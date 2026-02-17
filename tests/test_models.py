from kaizen.models import Guardrails, SozoGenerateResponse


def test_guardrails_to_dict():
    g = Guardrails(read_only=True, allow_tables=["users"], max_rows=100)
    assert g.to_dict() == {
        "readOnly": True,
        "allowTables": ["users"],
        "maxRows": 100,
    }


def test_sozo_response_exports():
    response = SozoGenerateResponse(
        columns=["name", "note"],
        rows=[{"name": "Alice", "note": 'He said "hi", then left'}],
        stats={},
    )
    assert response.to_csv() == 'name,note\nAlice,"He said ""hi"", then left"'
    assert response.to_jsonl() == '{"name": "Alice", "note": "He said \\"hi\\", then left"}'
