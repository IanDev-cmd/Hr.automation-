"""Payroll handoff. Full account numbers never enter the stored payload."""

from app.schemas import PayrollHandoffRequest, PayrollStoragePayload
from app.services.apps_script_client import AppsScriptClient

_STORE: dict[str, PayrollStoragePayload] = {}


def stored_handoff(candidate_id: str) -> PayrollStoragePayload | None:
    return _STORE.get(candidate_id)


def clear_handoffs() -> None:
    _STORE.clear()


def accept_handoff(body: PayrollHandoffRequest, client: AppsScriptClient) -> dict:
    storage = PayrollStoragePayload(
        candidate_id=body.candidate_id,
        bank_submitted=True,
        account_last4=body.account_last4(),
        p45_received=body.p45_received,
        starter_declaration=body.starter_declaration,
        emergency_name=body.emergency_name,
        emergency_phone=body.emergency_phone,
        job_description_signed=body.job_description_signed,
        working_time_opt_out=body.working_time_opt_out,
        key_phone_signed=body.key_phone_signed,
    )
    _STORE[body.candidate_id] = storage
    notice = client.dispatch(
        "PAYROLL_HANDOFF",
        {
            "candidate_id": body.candidate_id,
            "candidate_name": body.candidate_name,
            "home_name": body.home_name,
            "account_last4": storage.account_last4,
            "bank_submitted": True,
        },
    )
    return {
        "status": "OK",
        "candidate_id": body.candidate_id,
        "bank_submitted": True,
        "account_last4": storage.account_last4,
        "storage": storage.model_dump(),
        "apps_script": notice,
    }
