"""Request and response models for the HR desk API."""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

HomeName = Literal["Mayfield Lodge", "Rainbow Lodge", "Fernleigh House"]
SORT_CODE = r"^(?:\d{2}-\d{2}-\d{2}|\d{6})$"
ACCOUNT_NUMBER = r"^\d{6,10}$"


class PayCalculateRequest(BaseModel):
    home_name: HomeName
    expected_sleep_ins_per_week: int = Field(default=2, ge=0, le=14)
    employment_type: str = "Full-time"


class PayCalculateResponse(BaseModel):
    home_location: str
    region: str
    employment_type: str
    base_hourly_rate: float
    base_annual_salary: float
    sleep_in_rate_per_night: float
    projected_sleep_ins_annual: int
    annual_sleep_in_allowance: float
    total_gross_annual_package: float


class InterviewEvaluateRequest(BaseModel):
    interviewer_1_scores: dict[int, int]
    interviewer_2_scores: dict[int, int]

    @field_validator("interviewer_1_scores", "interviewer_2_scores")
    @classmethod
    def scores_in_range(cls, value: dict[int, int]) -> dict[int, int]:
        cleaned: dict[int, int] = {}
        for question_id, score in value.items():
            if isinstance(score, bool) or not isinstance(score, int):
                raise ValueError(f"question {question_id} score must be an integer")
            if question_id < 1 or question_id > 28:
                raise ValueError("question ids must be from 1 to 28")
            if score < 0 or score > 5:
                raise ValueError("scores must be from 0 to 5")
            cleaned[question_id] = score
        return cleaned


class ScoreDiscrepancy(BaseModel):
    question_id: int
    is_safeguarding: bool
    score_interviewer_1: int
    score_interviewer_2: int
    difference: int


class InterviewEvaluateResponse(BaseModel):
    interviewer_1_total: int
    interviewer_2_total: int
    average_score: float
    discrepancies_found: list[ScoreDiscrepancy]
    requires_consensus_discussion: bool
    can_proceed_to_offer: bool


class PayrollHandoffRequest(BaseModel):
    """Accept bank details once, then keep only the last four digits."""

    candidate_id: str = Field(min_length=1, max_length=80)
    candidate_name: str = ""
    home_name: str = ""
    sort_code: str = Field(pattern=SORT_CODE)
    account_number: str = Field(pattern=ACCOUNT_NUMBER)
    p45_received: bool = False
    starter_declaration: bool = False
    emergency_name: str = ""
    emergency_phone: str = ""
    job_description_signed: bool = False
    working_time_opt_out: bool = False
    key_phone_signed: bool = False

    def account_last4(self) -> str:
        return self.account_number[-4:]


class PayrollStoragePayload(BaseModel):
    """Shape written downstream. The full account number is not a field."""

    model_config = ConfigDict(extra="forbid")

    candidate_id: str
    bank_submitted: bool
    account_last4: str = Field(pattern=r"^\d{4}$")
    p45_received: bool
    starter_declaration: bool
    emergency_name: str
    emergency_phone: str
    job_description_signed: bool
    working_time_opt_out: bool
    key_phone_signed: bool


class PayrollHandoffResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["OK"] = "OK"
    candidate_id: str
    bank_submitted: bool
    account_last4: str = Field(pattern=r"^\d{4}$")
    storage: PayrollStoragePayload
    apps_script: dict[str, Any]


class GapHistoryRow(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str = ""
    gap: bool = False
    days: int = 0
    explanation: str = ""


class GapCheckRequest(BaseModel):
    history: list[GapHistoryRow]


class GapCheckResponse(BaseModel):
    gaps: list[dict[str, Any]]
    has_unexplained_gaps: bool


class DbsRecheckRequest(BaseModel):
    last_checked: str = Field(min_length=8)


class DbsRecheckResponse(BaseModel):
    due: bool
    interval_days: int
    last_checked: str
    message: str


class PurgeRecord(BaseModel):
    model_config = ConfigDict(extra="allow")

    candidate_id: str
    overall_status: str
    is_on_reapply_watchlist: bool = False
    rejected_at: str | None = None


class PurgeRequest(BaseModel):
    records: list[PurgeRecord]


class PurgeResponse(BaseModel):
    purge_ids: list[str]


class ErrorBody(BaseModel):
    status: Literal["ERROR"] = "ERROR"
    detail: str
