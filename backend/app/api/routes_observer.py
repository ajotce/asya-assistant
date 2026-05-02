from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps_auth import get_current_user, get_db_session
from app.db.models.common import ObservationStatus
from app.db.models.observation_rule import ObservationRule
from app.db.models.user import User
from app.models.schemas import (
    ObservationItemResponse,
    ObservationPostponeRequest,
    ObservationRuleItemResponse,
    ObservationRuleUpsertRequest,
)
from app.repositories.observation_rule_repository import ObservationRuleRepository
from app.services.observer_service import ObserverService

router = APIRouter(tags=["observer"])


def _to_rule_response(item: ObservationRule) -> ObservationRuleItemResponse:
    return ObservationRuleItemResponse(
        id=item.id,
        detector=item.detector,
        enabled=item.enabled,
        threshold_config=item.threshold_config,
        description=item.description,
        created_at=item.created_at.isoformat(),
        updated_at=item.updated_at.isoformat(),
    )


def _to_item_response(item) -> ObservationItemResponse:
    return ObservationItemResponse(
        id=item.id,
        detector=item.detector,
        title=item.title,
        details=item.details,
        severity=item.severity.value,
        status=item.status.value,
        context_payload=item.context_payload,
        observed_at=item.observed_at.isoformat(),
        postponed_until=(item.postponed_until.isoformat() if item.postponed_until else None),
        created_at=item.created_at.isoformat(),
        updated_at=item.updated_at.isoformat(),
    )


@router.get("/observer/rules", response_model=list[ObservationRuleItemResponse])
def list_observer_rules(
    current_user: User = Depends(get_current_user),
    db_session: Session = Depends(get_db_session),
) -> list[ObservationRuleItemResponse]:
    items = ObservationRuleRepository(db_session).list_for_user(current_user.id, only_enabled=False)
    return [_to_rule_response(item) for item in items]


@router.put("/observer/rules", response_model=ObservationRuleItemResponse)
def upsert_observer_rule(
    payload: ObservationRuleUpsertRequest,
    current_user: User = Depends(get_current_user),
    db_session: Session = Depends(get_db_session),
) -> ObservationRuleItemResponse:
    repo = ObservationRuleRepository(db_session)
    item = repo.get_by_detector_for_user(current_user.id, payload.detector)
    if item is None:
        item = ObservationRule(
            user_id=current_user.id,
            detector=payload.detector,
            enabled=payload.enabled,
            threshold_config=payload.threshold_config,
            description=payload.description,
        )
    else:
        item.enabled = payload.enabled
        item.threshold_config = payload.threshold_config
        item.description = payload.description
    repo.save(item)
    db_session.commit()
    db_session.refresh(item)
    return _to_rule_response(item)


@router.get("/observer/observations", response_model=list[ObservationItemResponse])
def list_observations(
    status: str | None = None,
    detector: str | None = None,
    limit: int = 100,
    current_user: User = Depends(get_current_user),
    db_session: Session = Depends(get_db_session),
) -> list[ObservationItemResponse]:
    parsed_status = None
    if status is not None:
        try:
            parsed_status = ObservationStatus(status)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Некорректный статус наблюдения") from exc
    items = ObserverService(db_session).list_observations(
        user_id=current_user.id,
        status=parsed_status,
        detector=detector,
        limit=limit,
    )
    return [_to_item_response(item) for item in items]


@router.post("/observer/observations/run")
def run_observer(
    current_user: User = Depends(get_current_user),
    db_session: Session = Depends(get_db_session),
) -> dict[str, int]:
    count = ObserverService(db_session).run_for_user(current_user)
    db_session.commit()
    return {"created": count}


@router.post("/observer/observations/{observation_id}/dismiss")
def dismiss_observation(
    observation_id: str,
    current_user: User = Depends(get_current_user),
    db_session: Session = Depends(get_db_session),
) -> dict[str, str]:
    try:
        ObserverService(db_session).dismiss(user_id=current_user.id, observation_id=observation_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"status": "ok"}


@router.post("/observer/observations/{observation_id}/actioned")
def actioned_observation(
    observation_id: str,
    current_user: User = Depends(get_current_user),
    db_session: Session = Depends(get_db_session),
) -> dict[str, str]:
    try:
        ObserverService(db_session).actioned(user_id=current_user.id, observation_id=observation_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"status": "ok"}


@router.post("/observer/observations/{observation_id}/postpone")
def postpone_observation(
    observation_id: str,
    payload: ObservationPostponeRequest,
    current_user: User = Depends(get_current_user),
    db_session: Session = Depends(get_db_session),
) -> dict[str, str]:
    try:
        postponed_until = datetime.fromisoformat(payload.postponed_until.replace("Z", "+00:00"))
        ObserverService(db_session).postpone(
            user_id=current_user.id,
            observation_id=observation_id,
            postponed_until=postponed_until,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"status": "ok"}
