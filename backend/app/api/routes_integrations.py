from __future__ import annotations

from datetime import date
from typing import NoReturn

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps_auth import get_current_user, get_db_session
from app.db.models.common import IntegrationProvider
from app.db.models.user import User
from app.integrations.bitrix24 import Bitrix24ConfigurationError, Bitrix24Service
from app.integrations.github import GitHubAPIError, GitHubAccessDeniedError, GitHubNotConnectedError, GitHubService
from app.integrations.imap import (
    ImapConfigurationError,
    ImapConnectionError,
    ImapMessageNotFoundError,
    ImapService,
    ImapSettings,
)
from app.models.schemas import (
    Bitrix24EntityResponse,
    Bitrix24ListResponse,
    Bitrix24PipelinesResponse,
    GitHubFileReadResponse,
    GitHubSearchResponse,
    ImapConnectRequest,
    ImapConnectionTestResponse,
    ImapFolderListResponse,
    ImapMessageDetailsResponse,
    ImapMessageSummaryResponse,
    IntegrationConnectionResponse,
)
from app.services.integration_connection_service import IntegrationConnectionService

router = APIRouter(tags=["integrations"])


def _parse_provider(raw: str) -> IntegrationProvider:
    try:
        return IntegrationProvider(raw)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Неподдерживаемый provider интеграции.") from exc


def _to_response(item) -> IntegrationConnectionResponse:
    return IntegrationConnectionResponse(
        provider=item.provider.value,
        status=item.status.value,
        scopes=item.scopes or [],
        connected_at=item.connected_at.isoformat() if item.connected_at else None,
        last_refresh_at=item.last_refresh_at.isoformat() if item.last_refresh_at else None,
        last_sync_at=item.last_sync_at.isoformat() if item.last_sync_at else None,
        safe_error_metadata=item.safe_error_metadata,
        created_at=item.created_at.isoformat() if item.created_at else None,
        updated_at=item.updated_at.isoformat() if item.updated_at else None,
    )


@router.get("/integrations", response_model=list[IntegrationConnectionResponse])
def list_integrations(
    current_user: User = Depends(get_current_user),
    db_session: Session = Depends(get_db_session),
) -> list[IntegrationConnectionResponse]:
    service = IntegrationConnectionService(db_session)
    connections = {item.provider: item for item in service.list_connections(user=current_user)}
    result = []
    for provider in IntegrationProvider:
        item = connections.get(provider) or service.get_connection_or_default(user=current_user, provider=provider)
        result.append(_to_response(item))
    return result


@router.get("/integrations/{provider}", response_model=IntegrationConnectionResponse)
def get_integration(
    provider: str,
    current_user: User = Depends(get_current_user),
    db_session: Session = Depends(get_db_session),
) -> IntegrationConnectionResponse:
    parsed_provider = _parse_provider(provider)
    service = IntegrationConnectionService(db_session)
    item = service.get_connection_or_default(user=current_user, provider=parsed_provider)
    return _to_response(item)


@router.delete("/integrations/{provider}", response_model=IntegrationConnectionResponse)
def disconnect_integration(
    provider: str,
    current_user: User = Depends(get_current_user),
    db_session: Session = Depends(get_db_session),
) -> IntegrationConnectionResponse:
    parsed_provider = _parse_provider(provider)
    service = IntegrationConnectionService(db_session)
    item = service.disconnect(user=current_user, provider=parsed_provider)
    return _to_response(item)


def _parse_optional_date(raw: str | None) -> date | None:
    if raw is None or raw == "":
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Дата должна быть в формате YYYY-MM-DD.") from exc


def _handle_imap_error(exc: Exception) -> NoReturn:
    if isinstance(exc, ImapConfigurationError):
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if isinstance(exc, ImapConnectionError):
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if isinstance(exc, ImapMessageNotFoundError):
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    raise exc


@router.post("/integrations/imap/test", response_model=ImapConnectionTestResponse)
def imap_test_connection(
    payload: ImapConnectRequest,
    current_user: User = Depends(get_current_user),
    db_session: Session = Depends(get_db_session),
) -> ImapConnectionTestResponse:
    _ = current_user
    service = ImapService(db_session)
    try:
        result = service.test_connection(
            settings=ImapSettings(
                email=payload.email,
                username=payload.username,
                password=payload.password,
                host=payload.host,
                port=payload.port,
                security=payload.security.lower(),
            )
        )
    except Exception as exc:  # noqa: BLE001
        _handle_imap_error(exc)
    return ImapConnectionTestResponse(ok=result["ok"], folders=result["folders"])


@router.post("/integrations/imap/connect", response_model=IntegrationConnectionResponse)
def imap_connect(
    payload: ImapConnectRequest,
    current_user: User = Depends(get_current_user),
    db_session: Session = Depends(get_db_session),
) -> IntegrationConnectionResponse:
    service = ImapService(db_session)
    try:
        service.connect(
            user=current_user,
            settings=ImapSettings(
                email=payload.email,
                username=payload.username,
                password=payload.password,
                host=payload.host,
                port=payload.port,
                security=payload.security.lower(),
            ),
        )
        connection = IntegrationConnectionService(db_session).get_connection_or_default(
            user=current_user,
            provider=IntegrationProvider.IMAP,
        )
    except Exception as exc:  # noqa: BLE001
        _handle_imap_error(exc)
    return _to_response(connection)


@router.get("/integrations/imap/folders", response_model=ImapFolderListResponse)
def imap_list_folders(
    current_user: User = Depends(get_current_user),
    db_session: Session = Depends(get_db_session),
) -> ImapFolderListResponse:
    service = ImapService(db_session)
    try:
        folders = service.list_folders(user_id=current_user.id)
    except Exception as exc:  # noqa: BLE001
        _handle_imap_error(exc)
    return ImapFolderListResponse(folders=folders)


@router.get("/integrations/imap/messages", response_model=list[ImapMessageSummaryResponse])
def imap_list_messages(
    folder: str = "INBOX",
    limit: int = 30,
    current_user: User = Depends(get_current_user),
    db_session: Session = Depends(get_db_session),
) -> list[ImapMessageSummaryResponse]:
    service = ImapService(db_session)
    try:
        items = service.list_messages(user_id=current_user.id, folder=folder, limit=limit)
    except Exception as exc:  # noqa: BLE001
        _handle_imap_error(exc)
    return [ImapMessageSummaryResponse(**item.__dict__) for item in items]


@router.get("/integrations/imap/messages/{uid}", response_model=ImapMessageDetailsResponse)
def imap_get_message(
    uid: str,
    folder: str = "INBOX",
    current_user: User = Depends(get_current_user),
    db_session: Session = Depends(get_db_session),
) -> ImapMessageDetailsResponse:
    service = ImapService(db_session)
    try:
        item = service.get_message(user_id=current_user.id, uid=uid, folder=folder)
    except Exception as exc:  # noqa: BLE001
        _handle_imap_error(exc)
    return ImapMessageDetailsResponse(**item.__dict__)


@router.get("/integrations/imap/search", response_model=list[ImapMessageSummaryResponse])
def imap_search_messages(
    q: str,
    folder: str = "INBOX",
    limit: int = 30,
    current_user: User = Depends(get_current_user),
    db_session: Session = Depends(get_db_session),
) -> list[ImapMessageSummaryResponse]:
    service = ImapService(db_session)
    try:
        items = service.search_messages(user_id=current_user.id, query=q, folder=folder, limit=limit)
    except Exception as exc:  # noqa: BLE001
        _handle_imap_error(exc)
    return [ImapMessageSummaryResponse(**item.__dict__) for item in items]


@router.post("/integrations/imap/messages/{uid}/read")
def imap_mark_as_read(
    uid: str,
    folder: str = "INBOX",
    current_user: User = Depends(get_current_user),
    db_session: Session = Depends(get_db_session),
) -> dict:
    service = ImapService(db_session)
    try:
        service.mark_as_read(user_id=current_user.id, uid=uid, folder=folder)
    except Exception as exc:  # noqa: BLE001
        _handle_imap_error(exc)
    return {"status": "ok"}


@router.delete("/integrations/imap", response_model=IntegrationConnectionResponse)
def imap_disconnect(
    current_user: User = Depends(get_current_user),
    db_session: Session = Depends(get_db_session),
) -> IntegrationConnectionResponse:
    service = ImapService(db_session)
    service.disconnect(user=current_user)
    item = IntegrationConnectionService(db_session).get_connection_or_default(user=current_user, provider=IntegrationProvider.IMAP)
    return _to_response(item)


@router.get("/integrations/bitrix24/leads", response_model=Bitrix24ListResponse)
def bitrix24_list_leads(
    source_id: str | None = None,
    created_since: str | None = None,
    current_user: User = Depends(get_current_user),
    db_session: Session = Depends(get_db_session),
) -> Bitrix24ListResponse:
    service = Bitrix24Service(db_session)
    try:
        data = service.list_leads(
            user_id=current_user.id,
            source_id=source_id,
            created_since=_parse_optional_date(created_since),
        )
    except Bitrix24ConfigurationError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return Bitrix24ListResponse(
        result=data.get("result", []),
        total=data.get("total"),
        next=data.get("next"),
    )


@router.get("/integrations/bitrix24/leads/{lead_id}", response_model=Bitrix24EntityResponse)
def bitrix24_get_lead(
    lead_id: int,
    current_user: User = Depends(get_current_user),
    db_session: Session = Depends(get_db_session),
) -> Bitrix24EntityResponse:
    service = Bitrix24Service(db_session)
    return Bitrix24EntityResponse(result=service.get_lead(user_id=current_user.id, lead_id=lead_id).get("result", {}))


@router.get("/integrations/bitrix24/deals", response_model=Bitrix24ListResponse)
def bitrix24_list_deals(
    date_from: str | None = None,
    date_to: str | None = None,
    current_user: User = Depends(get_current_user),
    db_session: Session = Depends(get_db_session),
) -> Bitrix24ListResponse:
    service = Bitrix24Service(db_session)
    data = service.list_deals(
        user_id=current_user.id,
        date_from=_parse_optional_date(date_from),
        date_to=_parse_optional_date(date_to),
    )
    return Bitrix24ListResponse(result=data.get("result", []), total=data.get("total"), next=data.get("next"))


@router.get("/integrations/bitrix24/deals/{deal_id}", response_model=Bitrix24EntityResponse)
def bitrix24_get_deal(
    deal_id: int,
    current_user: User = Depends(get_current_user),
    db_session: Session = Depends(get_db_session),
) -> Bitrix24EntityResponse:
    service = Bitrix24Service(db_session)
    return Bitrix24EntityResponse(result=service.get_deal(user_id=current_user.id, deal_id=deal_id).get("result", {}))


@router.get("/integrations/bitrix24/contacts", response_model=Bitrix24ListResponse)
def bitrix24_list_contacts(
    current_user: User = Depends(get_current_user),
    db_session: Session = Depends(get_db_session),
) -> Bitrix24ListResponse:
    service = Bitrix24Service(db_session)
    data = service.list_contacts(user_id=current_user.id)
    return Bitrix24ListResponse(result=data.get("result", []), total=data.get("total"), next=data.get("next"))


@router.get("/integrations/bitrix24/contacts/{contact_id}", response_model=Bitrix24EntityResponse)
def bitrix24_get_contact(
    contact_id: int,
    current_user: User = Depends(get_current_user),
    db_session: Session = Depends(get_db_session),
) -> Bitrix24EntityResponse:
    service = Bitrix24Service(db_session)
    return Bitrix24EntityResponse(
        result=service.get_contact(user_id=current_user.id, contact_id=contact_id).get("result", {})
    )


@router.get("/integrations/bitrix24/tasks", response_model=Bitrix24ListResponse)
def bitrix24_list_tasks(
    current_user: User = Depends(get_current_user),
    db_session: Session = Depends(get_db_session),
) -> Bitrix24ListResponse:
    service = Bitrix24Service(db_session)
    data = service.list_tasks(user_id=current_user.id)
    return Bitrix24ListResponse(result=data.get("result", []), total=data.get("total"), next=data.get("next"))


@router.get("/integrations/bitrix24/calls", response_model=Bitrix24ListResponse)
def bitrix24_list_calls(
    date_from: str | None = None,
    date_to: str | None = None,
    current_user: User = Depends(get_current_user),
    db_session: Session = Depends(get_db_session),
) -> Bitrix24ListResponse:
    service = Bitrix24Service(db_session)
    data = service.list_calls(
        user_id=current_user.id,
        date_from=_parse_optional_date(date_from),
        date_to=_parse_optional_date(date_to),
    )
    return Bitrix24ListResponse(result=data.get("result", []), total=data.get("total"), next=data.get("next"))


@router.get("/integrations/bitrix24/pipelines", response_model=Bitrix24PipelinesResponse)
def bitrix24_list_pipelines_stages_sources(
    current_user: User = Depends(get_current_user),
    db_session: Session = Depends(get_db_session),
) -> Bitrix24PipelinesResponse:
    service = Bitrix24Service(db_session)
    data = service.list_pipelines_stages_sources(user_id=current_user.id)
    return Bitrix24PipelinesResponse(
        pipelines=data["pipelines"],
        stages=data["stages"],
        sources=data["sources"],
    )


def _handle_github_error(exc: Exception) -> NoReturn:
    if isinstance(exc, GitHubNotConnectedError):
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if isinstance(exc, GitHubAccessDeniedError):
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    if isinstance(exc, GitHubAPIError):
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    raise exc


@router.get("/integrations/github/status", response_model=IntegrationConnectionResponse)
def github_status(
    current_user: User = Depends(get_current_user),
    db_session: Session = Depends(get_db_session),
) -> IntegrationConnectionResponse:
    service = IntegrationConnectionService(db_session)
    item = service.get_connection_or_default(user=current_user, provider=IntegrationProvider.GITHUB)
    return _to_response(item)


@router.get("/integrations/github/repos", response_model=list[dict])
def github_list_repos(
    visibility: str | None = None,
    per_page: int = 30,
    current_user: User = Depends(get_current_user),
    db_session: Session = Depends(get_db_session),
) -> list[dict]:
    service = GitHubService(db_session)
    try:
        return service.list_repositories(user=current_user, visibility=visibility, per_page=per_page)
    except Exception as exc:  # noqa: BLE001
        _handle_github_error(exc)


@router.get("/integrations/github/repos/{owner}/{repo}", response_model=dict)
def github_get_repo(
    owner: str,
    repo: str,
    current_user: User = Depends(get_current_user),
    db_session: Session = Depends(get_db_session),
) -> dict:
    service = GitHubService(db_session)
    try:
        return service.get_repository(user=current_user, owner=owner, repo=repo)
    except Exception as exc:  # noqa: BLE001
        _handle_github_error(exc)


@router.get("/integrations/github/repos/{owner}/{repo}/issues", response_model=list[dict])
def github_list_issues(
    owner: str,
    repo: str,
    state: str = "open",
    per_page: int = 30,
    current_user: User = Depends(get_current_user),
    db_session: Session = Depends(get_db_session),
) -> list[dict]:
    service = GitHubService(db_session)
    try:
        return service.list_issues(user=current_user, owner=owner, repo=repo, state=state, per_page=per_page)
    except Exception as exc:  # noqa: BLE001
        _handle_github_error(exc)


@router.get("/integrations/github/repos/{owner}/{repo}/pulls", response_model=list[dict])
def github_list_pulls(
    owner: str,
    repo: str,
    state: str = "open",
    per_page: int = 30,
    current_user: User = Depends(get_current_user),
    db_session: Session = Depends(get_db_session),
) -> list[dict]:
    service = GitHubService(db_session)
    try:
        return service.list_pull_requests(user=current_user, owner=owner, repo=repo, state=state, per_page=per_page)
    except Exception as exc:  # noqa: BLE001
        _handle_github_error(exc)


@router.get("/integrations/github/repos/{owner}/{repo}/commits", response_model=list[dict])
def github_list_commits(
    owner: str,
    repo: str,
    sha: str | None = None,
    per_page: int = 30,
    current_user: User = Depends(get_current_user),
    db_session: Session = Depends(get_db_session),
) -> list[dict]:
    service = GitHubService(db_session)
    try:
        return service.list_commits(user=current_user, owner=owner, repo=repo, sha=sha, per_page=per_page)
    except Exception as exc:  # noqa: BLE001
        _handle_github_error(exc)


@router.get("/integrations/github/repos/{owner}/{repo}/files", response_model=GitHubFileReadResponse)
def github_read_file(
    owner: str,
    repo: str,
    path: str,
    ref: str | None = None,
    current_user: User = Depends(get_current_user),
    db_session: Session = Depends(get_db_session),
) -> GitHubFileReadResponse:
    service = GitHubService(db_session)
    try:
        payload = service.read_file(user=current_user, owner=owner, repo=repo, path=path, ref=ref)
    except Exception as exc:  # noqa: BLE001
        _handle_github_error(exc)
    if payload.get("type") != "file":
        raise HTTPException(status_code=400, detail="Указанный path не является файлом.")
    return GitHubFileReadResponse(
        content=str(payload.get("content", "")),
        encoding=str(payload.get("encoding", "")),
        path=str(payload.get("path", path)),
        sha=str(payload.get("sha", "")),
        size=int(payload.get("size", 0)),
        html_url=payload.get("html_url"),
    )


@router.get("/integrations/github/search", response_model=GitHubSearchResponse)
def github_search(
    query: str,
    owner: str | None = None,
    repo: str | None = None,
    current_user: User = Depends(get_current_user),
    db_session: Session = Depends(get_db_session),
) -> GitHubSearchResponse:
    service = GitHubService(db_session)
    try:
        payload = service.search_code(user=current_user, query=query, owner=owner, repo=repo)
    except Exception as exc:  # noqa: BLE001
        _handle_github_error(exc)
    return GitHubSearchResponse(
        total_count=int(payload.get("total_count", 0)),
        incomplete_results=bool(payload.get("incomplete_results", False)),
        items=payload.get("items", []),
    )
