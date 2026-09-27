"""Inspect actual SDK request schemas without provider calls or credentials."""

import json
from typing import Any

import httpx
import pytest
from langchain_openai import ChatOpenAI
from pydantic import BaseModel

import main


def assert_strict_object_schemas(value: Any) -> None:
    """Check nested definitions as well as top-level structured-output objects."""
    if isinstance(value, dict):
        if value.get("type") == "object":
            assert value.get("additionalProperties") is False, value
            assert set(value.get("required", [])) == set(value.get("properties", {}))
        for child in value.values():
            assert_strict_object_schemas(child)
    elif isinstance(value, list):
        for child in value:
            assert_strict_object_schemas(child)


@pytest.mark.parametrize(
    "adapter_name,expected",
    [
        ("extractor", main.ChunkFindings()),
        ("reducer_llm", main.TenderAnalysis(categories=[])),
        ("report_llm", main.DecisionSupportReport(executive_summary="Test summary")),
        ("reconciliation_llm", main.ReconciliationDraft()),
        ("resolution_llm", main.PackageResolutionDraft()),
        (
            "compliance_report_llm",
            main.ComplianceReportDraft(
                requirements=[
                    main.RequirementEnrichment(
                        requirement_id="REQ-0001",
                        requirement_type="REQUIRED",
                        parameters=[
                            main.RequirementParameter(
                                name="insurance_limit", value="$5,000,000.50 CAD"
                            ),
                            main.RequirementParameter(
                                name="bid_security", value="10% of bid price"
                            ),
                        ],
                    )
                ]
            ),
        ),
    ],
)
def test_configured_adapters_send_closed_schemas_and_parse_responses(
    adapter_name: str, expected: BaseModel
) -> None:
    """Exercise production adapter configuration through the real OpenAI SDK."""
    requests: list[dict[str, Any]] = []

    def respond(request: httpx.Request) -> httpx.Response:
        """Validate the outgoing response format and supply a synthetic completion."""
        body = json.loads(request.content)
        requests.append(body)
        response_format = body["response_format"]
        assert response_format["type"] == "json_schema"
        assert response_format["json_schema"]["strict"] is True
        assert_strict_object_schemas(response_format["json_schema"]["schema"])
        return httpx.Response(
            200,
            json={
                "id": "chatcmpl-offline-schema-test",
                "object": "chat.completion",
                "created": 0,
                "model": "offline-schema-test",
                "choices": [
                    {
                        "index": 0,
                        "finish_reason": "stop",
                        "message": {
                            "role": "assistant",
                            "content": expected.model_dump_json(),
                        },
                    }
                ],
                "usage": {
                    "prompt_tokens": 1,
                    "completion_tokens": 1,
                    "total_tokens": 2,
                },
            },
        )

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        model = ChatOpenAI(
            model="offline-schema-test",
            api_key="offline-test-key",
            base_url="https://openai.invalid/v1",
            http_client=client,
            max_retries=0,
        )
        main.configure_model(model)
        result = getattr(main, adapter_name).invoke(
            "Test the structured output contract."
        )

    assert len(requests) == 1
    assert result == expected
