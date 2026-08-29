from mail_control.modules.analysis.openai import (
    PAYMENT_CLASSIFICATION_RULES,
    _response_text,
    _strict_schema,
)
from mail_control.modules.analysis.schemas import AnalysisResult


def test_openai_schema_is_strict() -> None:
    schema = _strict_schema(AnalysisResult.model_json_schema())

    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == set(schema["properties"])
    assert schema["$defs"]["Category"]["enum"]


def test_response_text_extracts_structured_output() -> None:
    payload = {
        "output": [
            {"type": "reasoning"},
            {
                "type": "message",
                "content": [{"type": "output_text", "text": '{"category":"Otros"}'}],
            },
        ]
    }

    assert _response_text(payload) == '{"category":"Otros"}'


def test_payment_rules_exclude_successful_updates() -> None:
    normalized = PAYMENT_CLASSIFICATION_RULES.lower()

    assert "métodos de pago actualizados" in normalized
    assert "pagos exitosos" in normalized
    assert "no generes alertas de pago" in normalized
