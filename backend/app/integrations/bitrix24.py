from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

import httpx
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models.common import IntegrationProvider
from app.services.encrypted_secret_service import EncryptedSecretService, SecretNotFoundError
from app.services.secret_crypto_service import SecretCryptoService


class Bitrix24ConfigurationError(ValueError):
    pass


@dataclass
class Bitrix24ConnectionConfig:
    base_url: str
    auth_mode: str
    auth_secret: str


class Bitrix24Integration:
    def __init__(self, config: Bitrix24ConnectionConfig, *, transport: httpx.BaseTransport | None = None) -> None:
        self._config = config
        self._client = httpx.Client(
            base_url=config.base_url.rstrip("/") + "/",
            timeout=httpx.Timeout(timeout=30.0, connect=10.0),
            transport=transport,
        )

    def close(self) -> None:
        self._client.close()

    def list_leads(self, *, start: int = 0, limit: int = 50, source_id: str | None = None, date_from: str | None = None) -> dict:
        filter_payload: dict[str, Any] = {}
        if source_id:
            filter_payload["SOURCE_ID"] = source_id
        if date_from:
            filter_payload[">=DATE_CREATE"] = date_from
        return self._call("crm.lead.list", {"start": start, "filter": filter_payload, "select": ["*"]}, limit=limit)

    def get_lead(self, *, lead_id: int) -> dict:
        return self._call("crm.lead.get", {"id": lead_id})

    def list_deals(self, *, start: int = 0, limit: int = 50, date_from: str | None = None, date_to: str | None = None) -> dict:
        filter_payload: dict[str, Any] = {}
        if date_from:
            filter_payload[">=DATE_CREATE"] = date_from
        if date_to:
            filter_payload["<=DATE_CREATE"] = date_to
        return self._call("crm.deal.list", {"start": start, "filter": filter_payload, "select": ["*"]}, limit=limit)

    def get_deal(self, *, deal_id: int) -> dict:
        return self._call("crm.deal.get", {"id": deal_id})

    def list_contacts(self, *, start: int = 0, limit: int = 50) -> dict:
        return self._call("crm.contact.list", {"start": start, "select": ["*"]}, limit=limit)

    def get_contact(self, *, contact_id: int) -> dict:
        return self._call("crm.contact.get", {"id": contact_id})

    def list_tasks(self, *, start: int = 0, limit: int = 50) -> dict:
        return self._call("tasks.task.list", {"start": start, "select": ["*"]}, limit=limit)

    def list_calls(self, *, start: int = 0, limit: int = 50, date_from: str | None = None, date_to: str | None = None) -> dict:
        filter_payload: dict[str, Any] = {}
        if date_from:
            filter_payload[">=CALL_START_DATE"] = date_from
        if date_to:
            filter_payload["<=CALL_START_DATE"] = date_to
        return self._call("voximplant.statistic.get", {"start": start, "FILTER": filter_payload}, limit=limit)

    def list_pipelines(self) -> dict:
        return self._call("crm.category.list", {"entityTypeId": 2})

    def list_stages(self, *, entity_id: str = "DEAL_STAGE") -> dict:
        return self._call("crm.status.list", {"filter": {"ENTITY_ID": entity_id}})

    def list_sources(self) -> dict:
        return self._call("crm.status.list", {"filter": {"ENTITY_ID": "SOURCE"}})

    def _call(self, method: str, payload: dict[str, Any], *, limit: int | None = None) -> dict:
        if limit is not None:
            payload["start"] = payload.get("start", 0)

        url = method
        if self._config.auth_mode == "oauth":
            payload = {**payload, "auth": self._config.auth_secret}
            response = self._client.post(url, json=payload)
        else:
            response = self._client.post(url, json=payload)
        response.raise_for_status()
        data = response.json()
        if isinstance(data, dict) and data.get("error"):
            raise RuntimeError(f"Bitrix24 API error: {data.get('error')}")
        return data


class Bitrix24Service:
    def __init__(self, session: Session, *, transport: httpx.BaseTransport | None = None) -> None:
        self._session = session
        self._settings = get_settings()
        self._secret_service = EncryptedSecretService(
            session,
            SecretCryptoService(self._settings.master_encryption_key),
        )
        self._transport = transport

    def list_leads(self, *, user_id: str, source_id: str | None = None, created_since: date | None = None) -> dict:
        date_from = created_since.isoformat() if created_since else None
        with self._integration_for_user(user_id=user_id) as integration:
            return integration.list_leads(source_id=source_id, date_from=date_from)

    def get_lead(self, *, user_id: str, lead_id: int) -> dict:
        with self._integration_for_user(user_id=user_id) as integration:
            return integration.get_lead(lead_id=lead_id)

    def list_deals(
        self,
        *,
        user_id: str,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> dict:
        with self._integration_for_user(user_id=user_id) as integration:
            return integration.list_deals(
                date_from=date_from.isoformat() if date_from else None,
                date_to=date_to.isoformat() if date_to else None,
            )

    def get_deal(self, *, user_id: str, deal_id: int) -> dict:
        with self._integration_for_user(user_id=user_id) as integration:
            return integration.get_deal(deal_id=deal_id)

    def list_contacts(self, *, user_id: str) -> dict:
        with self._integration_for_user(user_id=user_id) as integration:
            return integration.list_contacts()

    def get_contact(self, *, user_id: str, contact_id: int) -> dict:
        with self._integration_for_user(user_id=user_id) as integration:
            return integration.get_contact(contact_id=contact_id)

    def list_tasks(self, *, user_id: str) -> dict:
        with self._integration_for_user(user_id=user_id) as integration:
            return integration.list_tasks()

    def list_calls(self, *, user_id: str, date_from: date | None = None, date_to: date | None = None) -> dict:
        with self._integration_for_user(user_id=user_id) as integration:
            return integration.list_calls(
                date_from=date_from.isoformat() if date_from else None,
                date_to=date_to.isoformat() if date_to else None,
            )

    def list_pipelines_stages_sources(self, *, user_id: str) -> dict:
        with self._integration_for_user(user_id=user_id) as integration:
            return {
                "pipelines": integration.list_pipelines(),
                "stages": integration.list_stages(entity_id="DEAL_STAGE"),
                "sources": integration.list_sources(),
            }

    def _integration_for_user(self, *, user_id: str):
        cfg = self._load_config(user_id=user_id)
        integration = Bitrix24Integration(cfg, transport=self._transport)
        return _BitrixContext(integration)

    def _load_config(self, *, user_id: str) -> Bitrix24ConnectionConfig:
        try:
            base_url = self._secret_service.get_secret(user_id=user_id, name=self._secret_name("base_url"))
            auth_mode = self._secret_service.get_secret(user_id=user_id, name=self._secret_name("auth_mode"))
            auth_secret = self._secret_service.get_secret(user_id=user_id, name=self._secret_name("auth_secret"))
        except SecretNotFoundError as exc:
            raise Bitrix24ConfigurationError("Bitrix24 не подключен для текущего пользователя.") from exc
        if auth_mode not in {"webhook", "oauth"}:
            raise Bitrix24ConfigurationError("Некорректный режим авторизации Bitrix24.")
        return Bitrix24ConnectionConfig(base_url=base_url, auth_mode=auth_mode, auth_secret=auth_secret)

    @staticmethod
    def _secret_name(suffix: str) -> str:
        return f"integration:{IntegrationProvider.BITRIX24.value}:{suffix}"


class _BitrixContext:
    def __init__(self, integration: Bitrix24Integration) -> None:
        self._integration = integration

    def __enter__(self) -> Bitrix24Integration:
        return self._integration

    def __exit__(self, exc_type, exc, tb) -> None:
        self._integration.close()
