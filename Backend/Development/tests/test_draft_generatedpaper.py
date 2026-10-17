"""Round-trip test for the generatedPaper draft field (design §6, AC24-25).

Uses a minimal in-memory fake DynamoDB table that mimics the subset of the
boto3 Table API draft_service uses (put_item / get_item / update_item with a
SET expression). No real DynamoDB."""

from decimal import Decimal

import pytest

from models.draft_models import DraftResponse


class FakeTable:
    """Minimal fake of a boto3 DynamoDB Table for draft_service."""

    def __init__(self):
        self.items = {}

    @staticmethod
    def _key(k):
        return (k["userId"], k["draftId"])

    def put_item(self, Item):
        self.items[self._key(Item)] = dict(Item)

    def get_item(self, Key):
        item = self.items.get(self._key(Key))
        return {"Item": dict(item)} if item else {}

    def update_item(self, Key, UpdateExpression, ExpressionAttributeValues,
                    ExpressionAttributeNames, ReturnValues):
        item = self.items.setdefault(self._key(Key), dict(Key))
        # Parse "SET a = :a, #b = :b, ..." applying each assignment.
        assigns = UpdateExpression[len("SET "):].split(", ")
        for assign in assigns:
            lhs, rhs = [p.strip() for p in assign.split("=", 1)]
            name = ExpressionAttributeNames.get(lhs, lhs)
            value = ExpressionAttributeValues[rhs]
            item[name] = value
        self.items[self._key(Key)] = item
        return {"Attributes": dict(item)}

    def query(self, **kwargs):
        return {"Items": list(self.items.values())}

    def delete_item(self, Key, ReturnValues):
        return {}


@pytest.fixture
def service(monkeypatch):
    from services import draft_service as ds_module

    fake = FakeTable()
    svc = ds_module.DraftService.__new__(ds_module.DraftService)
    svc.table = fake
    return svc


def test_generatedpaper_roundtrip_and_questionpaper_unchanged(service):
    created = service.create_draft("u1", {
        "grade": "Grade 7", "subject": "Science",
        "questionPaper": {"q1": {"chapter": "Heat", "domain": "R/U", "images": []}},
    })
    draft_id = created["draftId"]

    pointer = {
        "s3Location": "s3://assessment-drafting-engine/Generated/u1/x/paper.json",
        "status": "completed",
        "generatedAt": "2024-01-01T00:00:00Z",
        "token_usage": {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15},
    }
    service.update_draft("u1", draft_id, {"generatedPaper": pointer, "status": "completed"})

    fetched = service.get_draft("u1", draft_id)
    # generatedPaper survived the round-trip.
    assert fetched["generatedPaper"]["s3Location"] == pointer["s3Location"]
    assert fetched["generatedPaper"]["token_usage"]["total_tokens"] == 15
    # questionPaper still round-trips unchanged (plus the derived generation_model).
    assert fetched["questionPaper"]["q1"]["chapter"] == "Heat"
    assert fetched["questionPaper"]["q1"]["generation_model"] == "sonnet-4.5"

    # DraftResponse serializes the field (no extra='allow', so the model edit matters).
    resp = DraftResponse(**fetched)
    assert resp.generatedPaper["status"] == "completed"


def test_generatedpaper_in_response_model_default_none():
    # The field is optional and defaults to None without breaking construction.
    resp = DraftResponse(
        draftId="d", userId="u", title="t", status="draft", step=1,
        createdAt="2024", updatedAt="2024",
    )
    assert resp.generatedPaper is None
