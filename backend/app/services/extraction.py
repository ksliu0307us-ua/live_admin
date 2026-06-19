"""Extraction pipeline: preprocess -> LLM extract -> validate -> persist."""

import hashlib
import json
import logging
from datetime import date

from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.config import settings
from app.logging_config import StepTimer, log_event
from app.models import Extraction
from app.schemas import LLMExtractionResult
from app.utils.preprocessor import preprocess_text

logger = logging.getLogger("app.extraction")


def _parse_date(value) -> date | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except (ValueError, TypeError):
            return None
    return None


def _parse_float(value) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def _parse_bool(value) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in ("true", "yes", "1")
    return None


def _get_field_value(field_data):
    if isinstance(field_data, dict) and "value" in field_data:
        return field_data["value"]
    return field_data


def _compute_overall_confidence(raw_result: dict) -> float:
    confidences = []
    for field_data in raw_result.values():
        if isinstance(field_data, dict) and "confidence" in field_data:
            conf = field_data["confidence"]
            if conf > 0:
                confidences.append(conf)
    if not confidences:
        return 0.0
    return round(sum(confidences) / len(confidences), 2)


def _build_field_confidences(raw_result: dict) -> dict:
    result = {}
    for field_name, field_data in raw_result.items():
        if isinstance(field_data, dict) and "confidence" in field_data:
            result[field_name] = {
                "value": field_data.get("value"),
                "confidence": field_data["confidence"],
                "explanation": field_data.get("explanation", ""),
            }
    return result


_EXPECTED_FIELDS = {
    "merchant", "document_type", "amount", "currency", "purchase_date",
    "subscription_status", "renewal_date", "free_trial_end_date",
    "return_deadline", "cancellation_deadline", "warranty_end_date",
    "cancellation_policy", "refund_opportunity", "price_increased",
    "old_price", "new_price", "detected_risk", "recommended_action",
    "explanation",
}


def _normalize_llm_result(raw_result: dict) -> dict:
    """Coerce each field into {value, confidence, explanation} format.

    Handles two common GPT failure modes:
    - Bare values (e.g. "USD" instead of {"value": "USD", "confidence": 0.9, ...})
    - Partial dicts missing 'confidence' or 'explanation' sub-fields
    """
    normalized = {}
    for key, val in raw_result.items():
        if key not in _EXPECTED_FIELDS:
            continue
        if isinstance(val, dict) and "value" in val:
            normalized[key] = {
                "value": val["value"],
                "confidence": val.get("confidence", 0.7),
                "explanation": val.get("explanation", ""),
            }
        else:
            normalized[key] = {
                "value": val,
                "confidence": 0.7 if val is not None else 0.0,
                "explanation": "",
            }
    return normalized


def _extract_with_fallback(cleaned_text: str) -> tuple[dict, str]:
    """Try primary LLM client; fall back to mock on failure. Returns (result, source)."""
    from app.llm.client import get_llm_client

    client = get_llm_client()
    source = "mock" if settings.use_mock_llm else "openai"

    try:
        raw_result = client.extract(cleaned_text)
    except Exception as e:
        log_event(logger, logging.WARNING, "extraction_llm_failed",
                  error=str(e), original_source=source)
        if not settings.use_mock_llm:
            log_event(logger, logging.INFO, "extraction_fallback_to_mock")
            from app.llm.mock import MockLLMClient
            raw_result = MockLLMClient().extract(cleaned_text)
            source = "mock_fallback"
        else:
            raise

    if source != "mock":
        raw_result = _normalize_llm_result(raw_result)
        log_event(logger, logging.DEBUG, "extraction_normalized",
                  source=source, field_count=len(raw_result))

    try:
        LLMExtractionResult.model_validate(raw_result)
        log_event(logger, logging.DEBUG, "extraction_validation_passed", source=source)
    except ValidationError as e:
        log_event(logger, logging.WARNING, "extraction_validation_failed",
                  error=str(e), source=source, field_count=len(raw_result))
        if not settings.use_mock_llm:
            log_event(logger, logging.INFO, "extraction_fallback_to_mock_validation")
            from app.llm.mock import MockLLMClient
            raw_result = MockLLMClient().extract(cleaned_text)
            source = "mock_fallback"

    return raw_result, source


def _compute_content_hash(text: str) -> str:
    normalized = " ".join(text.lower().split())
    return hashlib.sha256(normalized.encode()).hexdigest()


def _str_val(raw_result: dict, field: str) -> str | None:
    v = _get_field_value(raw_result.get(field))
    return v if isinstance(v, str) else None


def run_extraction(input_text: str, input_type: str, db: Session, user_id: str) -> Extraction:
    """Run the full extraction pipeline and persist results."""
    with StepTimer() as total_timer:

        # Step 1: preprocess
        with StepTimer() as pp_timer:
            cleaned = preprocess_text(input_text)
            content_hash = _compute_content_hash(input_text)
        log_event(logger, logging.INFO, "step_preprocess",
                  user_id=user_id, input_type=input_type,
                  raw_chars=len(input_text), cleaned_chars=len(cleaned),
                  content_hash=content_hash[:12], elapsed_ms=pp_timer.elapsed_ms)

        # Step 2: duplicate check
        with StepTimer() as dup_timer:
            existing = db.query(Extraction).filter(
                Extraction.user_id == user_id,
                Extraction.content_hash == content_hash,
            ).first()
            is_dup = existing is not None
        log_event(logger, logging.INFO, "step_duplicate_check",
                  user_id=user_id, is_duplicate=is_dup,
                  duplicate_of=existing.id if existing else None,
                  elapsed_ms=dup_timer.elapsed_ms)

        # Step 3: LLM extraction
        with StepTimer() as llm_timer:
            raw_result, source = _extract_with_fallback(cleaned)
        merchant = _str_val(raw_result, "merchant")
        doc_type = _str_val(raw_result, "document_type")
        confidence = _compute_overall_confidence(raw_result)
        log_event(logger, logging.INFO, "step_llm_extract",
                  user_id=user_id, source=source,
                  merchant=merchant, document_type=doc_type,
                  confidence_score=confidence,
                  fields_returned=len(raw_result),
                  elapsed_ms=llm_timer.elapsed_ms)

        # Step 4: persist
        with StepTimer() as db_timer:
            extraction = Extraction(
                user_id=user_id,
                raw_input=input_text,
                input_type=input_type,
                content_hash=content_hash,
                is_duplicate=is_dup,
                duplicate_of_id=existing.id if existing else None,
                merchant=merchant,
                document_type=doc_type,
                amount=_parse_float(_get_field_value(raw_result.get("amount"))),
                currency=_str_val(raw_result, "currency") or "USD",
                purchase_date=_parse_date(_get_field_value(raw_result.get("purchase_date"))),
                subscription_status=_str_val(raw_result, "subscription_status"),
                renewal_date=_parse_date(_get_field_value(raw_result.get("renewal_date"))),
                free_trial_end_date=_parse_date(_get_field_value(raw_result.get("free_trial_end_date"))),
                return_deadline=_parse_date(_get_field_value(raw_result.get("return_deadline"))),
                cancellation_deadline=_parse_date(_get_field_value(raw_result.get("cancellation_deadline"))),
                warranty_end_date=_parse_date(_get_field_value(raw_result.get("warranty_end_date"))),
                cancellation_policy=_str_val(raw_result, "cancellation_policy"),
                refund_opportunity=_str_val(raw_result, "refund_opportunity"),
                price_increased=_parse_bool(_get_field_value(raw_result.get("price_increased"))),
                old_price=_parse_float(_get_field_value(raw_result.get("old_price"))),
                new_price=_parse_float(_get_field_value(raw_result.get("new_price"))),
                detected_risk=_str_val(raw_result, "detected_risk"),
                recommended_action=_str_val(raw_result, "recommended_action"),
                explanation=_str_val(raw_result, "explanation"),
                confidence_score=confidence,
                field_confidences=json.dumps(_build_field_confidences(raw_result)),
                raw_llm_response=json.dumps(raw_result),
            )
            db.add(extraction)
            db.commit()
            db.refresh(extraction)
        log_event(logger, logging.INFO, "step_persist",
                  user_id=user_id, extraction_id=extraction.id,
                  elapsed_ms=db_timer.elapsed_ms)

    log_event(logger, logging.INFO, "extraction_complete",
              user_id=user_id, extraction_id=extraction.id,
              merchant=merchant, document_type=doc_type,
              confidence_score=confidence, source=source,
              is_duplicate=is_dup,
              total_elapsed_ms=total_timer.elapsed_ms)

    return extraction
