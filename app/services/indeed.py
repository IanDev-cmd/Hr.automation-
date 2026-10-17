"""Indeed Apply import. Four screening answers decide the queue."""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from app.db import connection, home_id

MIN_YEARS = 1.0


def _yes(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    text = str(value or "").strip().lower()
    if text in {"yes", "y", "true", "held", "1"}:
        return True
    if text in {"no", "n", "false", "0", "none"}:
        return False
    return None


def _years(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    number = ""
    for char in text:
        if char.isdigit() or char == ".":
            number += char
        elif number:
            break
    if not number:
        return None
    return float(number)


def _question_text(item: dict) -> str:
    question = item.get("question") or {}
    if isinstance(question, str):
        return question.lower()
    return f"{question.get('id', '')} {question.get('question', '')}".lower()


def _answer_value(item: dict) -> Any:
    answer = item.get("answer")
    if isinstance(answer, dict):
        return answer.get("value") or answer.get("label") or ""
    return answer


def normalize_application(payload: dict) -> dict[str, Any]:
    applicant = payload.get("applicant") or {}
    job = payload.get("job") or {}
    full_name = payload.get("full_name") or applicant.get("fullName") or applicant.get("full_name") or ""
    email = payload.get("email") or applicant.get("email") or ""
    phone = payload.get("phone") or applicant.get("phoneNumber") or applicant.get("phone") or ""
    home_name = payload.get("home_name") or job.get("location") or "Mayfield Lodge"
    for name in ("Mayfield Lodge", "Rainbow Lodge", "Fernleigh House"):
        if name.lower() in str(home_name).lower():
            home_name = name
            break
    else:
        home_name = "Mayfield Lodge"

    answers = {
        "nvq_level_3": payload.get("nvq_level_3"),
        "driving_licence_one_year": payload.get("driving_licence_one_year"),
        "right_to_work": payload.get("right_to_work"),
        "years_experience": payload.get("years_experience"),
    }
    screen = payload.get("screenerQuestionsAndAnswers") or {}
    for item in screen.get("questionsAndAnswers") or payload.get("questions") or []:
        label = _question_text(item)
        value = _answer_value(item)
        if "nvq" in label or "level 3" in label:
            answers["nvq_level_3"] = _yes(value)
        elif "driv" in label or "licence" in label or "license" in label:
            answers["driving_licence_one_year"] = _yes(value)
        elif "right to work" in label or label.strip() in {"rtw", "uk_right_to_work"}:
            answers["right_to_work"] = _yes(value)
        elif "experience" in label or "years" in label:
            answers["years_experience"] = _years(value)

    if not isinstance(answers["nvq_level_3"], bool):
        answers["nvq_level_3"] = _yes(answers["nvq_level_3"])
    if not isinstance(answers["driving_licence_one_year"], bool):
        answers["driving_licence_one_year"] = _yes(answers["driving_licence_one_year"])
    if not isinstance(answers["right_to_work"], bool):
        answers["right_to_work"] = _yes(answers["right_to_work"])
    if not isinstance(answers["years_experience"], (int, float)):
        answers["years_experience"] = _years(answers["years_experience"])

    return {
        "full_name": str(full_name).strip(),
        "email": str(email).strip(),
        "phone": str(phone).strip(),
        "home_name": home_name,
        "nvq_level_3": answers["nvq_level_3"],
        "driving_licence_one_year": answers["driving_licence_one_year"],
        "right_to_work": answers["right_to_work"],
        "years_experience": answers["years_experience"],
    }


def screen_reasons(application: dict) -> list[str]:
    reasons = []
    if application["nvq_level_3"] is not True:
        reasons.append("NVQ Level 3 in Residential Childcare is not held")
    if application["driving_licence_one_year"] is not True:
        reasons.append("UK driving licence has not been held for at least 1 year")
    if application["right_to_work"] is not True:
        reasons.append("UK Right to Work was not confirmed")
    years = application["years_experience"]
    if years is None or years < MIN_YEARS:
        reasons.append("Insufficient UK Children's Support Worker experience")
    return reasons


def import_application(payload: dict) -> dict[str, Any]:
    application = normalize_application(payload)
    if not application["full_name"]:
        raise ValueError("Candidate name is required")
    if home_id(application["home_name"]) is None:
        raise ValueError("Home is not one of the Sequel houses")
    reasons = screen_reasons(application)
    now = datetime.now(timezone.utc)
    candidate_id = "ind_" + uuid.uuid4().hex[:12]
    tags = []
    if application["nvq_level_3"]:
        tags.append("nvq-level-3")
    if application["driving_licence_one_year"]:
        tags.append("uk-licence")
    if application["years_experience"]:
        tags.append(f"experience-{application['years_experience']}")
    stage = "prescreen" if not reasons else "historic"
    rejected_at = None if not reasons else now.isoformat()
    eligible = None if not reasons else (now + timedelta(days=180)).isoformat()
    db = connection()
    db.execute(
        """
        INSERT INTO candidates (
          id, full_name, email, phone, home_id, stage, applied_at, rejected_at,
          on_reapply_watchlist, completion_percent, rejection_reason, reapply_eligible_at, skills_tags, source
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?, 'indeed')
        """,
        (
            candidate_id,
            application["full_name"],
            application["email"],
            application["phone"],
            home_id(application["home_name"]),
            stage,
            now.isoformat(),
            rejected_at,
            1 if reasons else 0,
            "; ".join(reasons),
            eligible,
            ",".join(tags),
        ),
    )
    db.execute(
        """
        INSERT INTO screening_answers (
          candidate_id, nvq_level_3, driving_licence_one_year, right_to_work, years_experience
        ) VALUES (?, ?, ?, ?, ?)
        """,
        (
            candidate_id,
            1 if application["nvq_level_3"] else 0,
            1 if application["driving_licence_one_year"] else 0,
            1 if application["right_to_work"] else 0,
            float(application["years_experience"] or 0),
        ),
    )
    db.commit()
    return {
        "candidate_id": candidate_id,
        "full_name": application["full_name"],
        "home_name": application["home_name"],
        "stage": stage,
        "rejection_reason": "; ".join(reasons),
        "skills_tags": tags,
        "screening": {
            "nvq_level_3": bool(application["nvq_level_3"]),
            "driving_licence_one_year": bool(application["driving_licence_one_year"]),
            "right_to_work": bool(application["right_to_work"]),
            "years_experience": float(application["years_experience"] or 0),
        },
    }
