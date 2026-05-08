from __future__ import annotations

import base64
import hmac
import ipaddress
import logging
from typing import Any

from fastapi import FastAPI, HTTPException, Request, Response, status
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, generate_latest
from prometheus_fastapi_instrumentator import Instrumentator
from sqlalchemy import text

from app.core.config import Settings
from app.db.models.common import IntegrationConnectionStatus, IntegrationProvider
from app.db.session import create_session, get_engine

LOGGER = logging.getLogger(__name__)

http_requests_total = Counter(
    "asya_http_requests_total",
    "Total HTTP requests handled by Asya.",
    ["method", "route", "status_code"],
)

http_request_latency_seconds = Counter(
    "asya_http_request_duration_seconds_sum",
    "Total request latency (seconds), can be used to compute average latency.",
    ["method", "route"],
)

integration_api_calls_total = Counter(
    "asya_integration_api_calls_total",
    "Total external integration API calls.",
    ["provider", "operation", "status"],
)

llm_tokens_used_total = Counter(
    "asya_llm_tokens_used_total",
    "LLM tokens used by kind/model.",
    ["kind", "model"],
)

active_sessions_gauge = Gauge(
    "asya_active_sessions",
    "Number of non-revoked active auth sessions.",
)

expired_integration_tokens_gauge = Gauge(
    "asya_expired_integration_tokens",
    "Number of integration connections marked as expired.",
    ["provider"],
)

db_pool_checked_out_gauge = Gauge(
    "asya_db_pool_checked_out",
    "Checked out DB connections in SQLAlchemy pool.",
)

llm_provider_up_gauge = Gauge(
    "asya_llm_provider_up",
    "VseLLM provider availability probe result (1=up, 0=down).",
)


def setup_metrics(app: FastAPI, settings: Settings) -> None:
    if not settings.metrics_enabled:
        LOGGER.info("Metrics collection is disabled via METRICS_ENABLED.")
        return

    Instrumentator(
        should_group_status_codes=False,
        should_ignore_untemplated=True,
        should_respect_env_var=False,
        excluded_handlers=["/healthz", "/readyz"],
    ).instrument(app)

    @app.middleware("http")
    async def _http_metrics_middleware(request: Request, call_next):
        response = await call_next(request)
        route = request.scope.get("route")
        route_name = getattr(route, "path", request.url.path)
        method = request.method.upper()
        status_code = str(response.status_code)
        http_requests_total.labels(method=method, route=route_name, status_code=status_code).inc()
        latency = _extract_latency_seconds(response)
        if latency is not None:
            http_request_latency_seconds.labels(method=method, route=route_name).inc(latency)
        return response

    @app.get(settings.metrics_path, include_in_schema=False)
    def metrics_endpoint(request: Request) -> Response:
        _assert_metrics_access(request, settings)
        _refresh_runtime_gauges(settings)
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


def observe_integration_api_call(provider: str, operation: str, success: bool) -> None:
    status_value = "success" if success else "error"
    integration_api_calls_total.labels(provider=provider, operation=operation, status=status_value).inc()


def observe_llm_tokens(kind: str, model: str, total_tokens: int | None) -> None:
    if not total_tokens or total_tokens <= 0:
        return
    llm_tokens_used_total.labels(kind=kind, model=(model or "unknown")[:255]).inc(total_tokens)


def _refresh_runtime_gauges(settings: Settings) -> None:
    _refresh_active_sessions()
    _refresh_expired_integration_tokens()
    _refresh_db_pool_checked_out(settings)
    _refresh_llm_provider_health()


def _refresh_active_sessions() -> None:
    try:
        db = create_session()
        try:
            value = int(
                db.execute(
                    text(
                        "SELECT COUNT(*) FROM auth_sessions "
                        "WHERE revoked_at IS NULL AND expires_at > CURRENT_TIMESTAMP"
                    )
                ).scalar()
                or 0
            )
        finally:
            db.close()
    except Exception:  # noqa: BLE001
        value = 0
    active_sessions_gauge.set(value)


def _refresh_expired_integration_tokens() -> None:
    for provider in IntegrationProvider:
        expired_integration_tokens_gauge.labels(provider=provider.value).set(0)

    try:
        db = create_session()
        try:
            rows = db.execute(
                text(
                    "SELECT provider, COUNT(*) FROM integration_connections "
                    "WHERE status = :status GROUP BY provider"
                ),
                {"status": IntegrationConnectionStatus.EXPIRED.value},
            ).all()
        finally:
            db.close()
    except Exception:  # noqa: BLE001
        return

    for provider, count in rows:
        expired_integration_tokens_gauge.labels(provider=str(provider)).set(int(count or 0))


def _refresh_db_pool_checked_out(settings: Settings) -> None:
    checked_out = 0
    try:
        engine = get_engine(settings.asya_db_url)
        pool = getattr(engine, "pool", None)
        checked_out_fn = getattr(pool, "checkedout", None)
        if callable(checked_out_fn):
            checked_out = int(checked_out_fn())
    except Exception:  # noqa: BLE001
        checked_out = 0
    db_pool_checked_out_gauge.set(checked_out)


def _refresh_llm_provider_health() -> None:
    try:
        from app.api.routes_health import check_vsellm_reachable

        reachable, _ = check_vsellm_reachable()
        if reachable is None:
            llm_provider_up_gauge.set(1)
            return
        llm_provider_up_gauge.set(1 if reachable else 0)
    except Exception:  # noqa: BLE001
        llm_provider_up_gauge.set(0)


def _extract_latency_seconds(response: Response) -> float | None:
    process_time = response.headers.get("X-Process-Time")
    if process_time is None:
        return None
    try:
        value = float(process_time)
    except ValueError:
        return None
    return value if value >= 0 else None


def _assert_metrics_access(request: Request, settings: Settings) -> None:
    if _is_basic_auth_enabled(settings):
        _assert_basic_auth(request, settings)
        return
    _assert_ip_allowlist(request, settings)


def _is_basic_auth_enabled(settings: Settings) -> bool:
    return bool(settings.metrics_basic_auth_username and settings.metrics_basic_auth_password)


def _assert_basic_auth(request: Request, settings: Settings) -> None:
    header = request.headers.get("Authorization", "")
    if not header.startswith("Basic "):
        _raise_metrics_auth_error()

    token = header[len("Basic ") :].strip()
    try:
        decoded = base64.b64decode(token).decode("utf-8")
    except Exception:  # noqa: BLE001
        _raise_metrics_auth_error()
        return

    username, separator, password = decoded.partition(":")
    if not separator:
        _raise_metrics_auth_error()

    username_ok = hmac.compare_digest(username, settings.metrics_basic_auth_username)
    password_ok = hmac.compare_digest(password, settings.metrics_basic_auth_password)
    if not (username_ok and password_ok):
        _raise_metrics_auth_error()


def _assert_ip_allowlist(request: Request, settings: Settings) -> None:
    allowed_raw = [item.strip() for item in settings.metrics_ip_allowlist.split(",") if item.strip()]
    if not allowed_raw:
        _raise_metrics_auth_error()

    client_host = request.client.host if request.client else ""
    if not _is_client_allowed(client_host, allowed_raw):
        _raise_metrics_auth_error()


def _is_client_allowed(client_host: str, allowed_raw: list[str]) -> bool:
    for entry in allowed_raw:
        if "/" in entry:
            try:
                network = ipaddress.ip_network(entry, strict=False)
                if ipaddress.ip_address(client_host) in network:
                    return True
            except ValueError:
                continue
            continue
        if client_host == entry:
            return True
    return False


def _raise_metrics_auth_error() -> None:
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Unauthorized metrics access.",
        headers={"WWW-Authenticate": "Basic"},
    )


def sanitize_sentry_payload(value: Any) -> Any:
    if isinstance(value, dict):
        sanitized: dict[str, Any] = {}
        for key, item in value.items():
            normalized_key = str(key).lower()
            if _is_sensitive_key(normalized_key):
                sanitized[key] = "[REDACTED]"
                continue
            sanitized[key] = sanitize_sentry_payload(item)
        return sanitized
    if isinstance(value, list):
        return [sanitize_sentry_payload(item) for item in value]
    return value


def _is_sensitive_key(key: str) -> bool:
    sensitive_tokens = (
        "authorization",
        "cookie",
        "token",
        "password",
        "secret",
        "api_key",
        "apikey",
        "session",
    )
    return any(token in key for token in sensitive_tokens)
