"""Tests for LLM output validation and fallback behavior."""

from unittest.mock import MagicMock, patch

from pydantic import ValidationError

from app.schemas import LLMExtractionResult
from app import config as config_module


def test_valid_llm_json():
    valid_data = {
        "merchant": {"value": "Netflix", "confidence": 0.99, "explanation": "Named in email"},
        "document_type": {"value": "subscription", "confidence": 0.90, "explanation": "Sub email"},
        "amount": {"value": 22.99, "confidence": 0.95, "explanation": "Price stated"},
    }
    result = LLMExtractionResult.model_validate(valid_data)
    assert result.merchant.value == "Netflix"


def test_invalid_llm_json_bad_confidence():
    invalid_data = {
        "merchant": {"value": "Netflix", "confidence": 5.0, "explanation": "Too high"},
    }
    try:
        LLMExtractionResult.model_validate(invalid_data)
        assert False, "Should have raised ValidationError"
    except ValidationError:
        pass


def test_invalid_llm_json_missing_subfields():
    invalid_data = {"merchant": {"value": "Netflix"}}
    try:
        LLMExtractionResult.model_validate(invalid_data)
        assert False, "Should have raised ValidationError"
    except ValidationError:
        pass


def test_missing_fields_graceful():
    sparse_data = {"merchant": {"value": "Test", "confidence": 0.5, "explanation": "test"}}
    result = LLMExtractionResult.model_validate(sparse_data)
    assert result.merchant.value == "Test"
    assert result.amount is None


def test_unknown_document_type_extraction(client, auth_headers):
    resp = client.post(
        "/api/extract",
        json={
            "input_text": "Dear valued customer, we hope you are enjoying our services. Please let us know if you have any feedback.",
            "input_type": "paste",
        },
        headers=auth_headers,
    )
    assert resp.status_code == 201
    assert resp.json()["extraction"]["document_type"] == "unknown"


def test_fallback_on_llm_failure(client, auth_headers):
    mock_client = MagicMock()
    mock_client.extract.side_effect = Exception("API error")

    original_key = config_module.settings.openai_api_key
    try:
        object.__setattr__(config_module.settings, "openai_api_key", "fake-key")
        with patch("app.llm.client.get_llm_client", return_value=mock_client):
            resp = client.post(
                "/api/extract",
                json={
                    "input_text": "Your Netflix membership will renew soon for $22.99. Cancel at netflix.com/account.",
                    "input_type": "paste",
                },
                headers=auth_headers,
            )
            assert resp.status_code == 201
            assert resp.json()["extraction"]["merchant"] == "Netflix"
    finally:
        object.__setattr__(config_module.settings, "openai_api_key", original_key)
