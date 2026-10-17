"""HR routes. Validation stays here; figures stay in the domain engines."""

import datetime

from fastapi import APIRouter, Depends, HTTPException

from app.config import Settings, get_settings
from app.schemas import (
    DbsRecheckRequest,
    DbsRecheckResponse,
    GapCheckRequest,
    GapCheckResponse,
    InterviewEvaluateRequest,
    InterviewEvaluateResponse,
    PayCalculateRequest,
    PayCalculateResponse,
    PayrollHandoffRequest,
    PayrollHandoffResponse,
    PurgeRequest,
    PurgeResponse,
)
from app.services.apps_script_client import AppsScriptClient
from app.services.payroll import accept_handoff, stored_handoff
from hr_automata.dbs import dbs_recheck_due
from hr_automata.gaps import unexplained_gaps
from hr_automata.pay import PayAndAllowanceCalculator
from hr_automata.purge import GDPRDataPurgeWorker
from hr_automata.scoring import InterviewScoringAggregator

router = APIRouter(prefix="/api/v1/hr", tags=["hr"])
_pay = PayAndAllowanceCalculator()
_scores = InterviewScoringAggregator()
_purge = GDPRDataPurgeWorker()


def script_client(settings: Settings = Depends(get_settings)) -> AppsScriptClient:
    return AppsScriptClient(settings)


@router.post("/pay/calculate", response_model=PayCalculateResponse)
def calculate_pay(body: PayCalculateRequest) -> PayCalculateResponse:
    package = _pay.calculate_offer_package(
        body.home_name,
        body.expected_sleep_ins_per_week,
        body.employment_type,
    )
    return PayCalculateResponse.model_validate(package)


@router.post("/interviews/evaluate", response_model=InterviewEvaluateResponse)
def evaluate_interview(body: InterviewEvaluateRequest) -> InterviewEvaluateResponse:
    try:
        result = _scores.evaluate_panel_scores(body.interviewer_1_scores, body.interviewer_2_scores)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return InterviewEvaluateResponse.model_validate(result)


@router.post("/payroll/handoff", response_model=PayrollHandoffResponse)
def payroll_handoff(
    body: PayrollHandoffRequest,
    client: AppsScriptClient = Depends(script_client),
) -> PayrollHandoffResponse:
    return PayrollHandoffResponse.model_validate(accept_handoff(body, client))


@router.get("/payroll/handoff/{candidate_id}")
def read_payroll_handoff(candidate_id: str) -> dict:
    stored = stored_handoff(candidate_id)
    if stored is None:
        raise HTTPException(status_code=404, detail="Payroll handoff not found")
    return {"status": "OK", "storage": stored.model_dump()}


@router.post("/gaps/check", response_model=GapCheckResponse)
def check_gaps(body: GapCheckRequest) -> GapCheckResponse:
    rows = [row.model_dump() for row in body.history]
    open_rows = unexplained_gaps(rows)
    return GapCheckResponse(gaps=open_rows, has_unexplained_gaps=bool(open_rows))


@router.post("/dbs/recheck", response_model=DbsRecheckResponse)
def dbs_recheck(body: DbsRecheckRequest) -> DbsRecheckResponse:
    try:
        due = dbs_recheck_due(body.last_checked)
        checked = datetime.datetime.fromisoformat(body.last_checked.replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail="last_checked must be an ISO date") from exc
    if checked.tzinfo is None:
        checked = checked.replace(tzinfo=datetime.timezone.utc)
    days = (datetime.datetime.now(datetime.timezone.utc) - checked).days
    if due:
        message = f"Last Update Service check {body.last_checked} is {days} days ago. A 90-day recheck is due."
    else:
        message = f"Last Update Service check {body.last_checked}. Next recheck in {90 - days} days."
    return DbsRecheckResponse(due=due, interval_days=90, last_checked=body.last_checked, message=message)


@router.post("/gdpr/purge", response_model=PurgeResponse)
def preview_purge(body: PurgeRequest) -> PurgeResponse:
    records = [row.model_dump() for row in body.records]
    return PurgeResponse(purge_ids=_purge.identify_purgeable_records(records))
