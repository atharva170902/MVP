"""Tests for the /api/generate routes (design §5). FastAPI TestClient with
generation + persistence + draft_service monkeypatched; no real AWS."""

import pytest
from fastapi.testclient import TestClient

import main
from services.job_store import job_store


@pytest.fixture
def client(monkeypatch):
    # In-memory draft store keyed by (user, draft).
    store = {
        ("u1", "draft-ok"): {
            "draftId": "draft-ok", "userId": "u1", "grade": "Grade 7",
            "subject": "Science", "examType": "PT",
            "questionPaper": {"q1": {"chapter": "Heat", "domain": "R/U", "images": []}},
        },
        ("u1", "draft-empty"): {
            "draftId": "draft-empty", "userId": "u1", "questionPaper": {},
        },
    }

    def fake_get_draft(user_id, draft_id):
        return store.get((user_id, draft_id))

    updates = []

    def fake_update_draft(user_id, draft_id, upd):
        updates.append((user_id, draft_id, upd))
        d = store.get((user_id, draft_id))
        if d is not None:
            d.update(upd)
        return d

    monkeypatch.setattr(main.draft_service, "get_draft", fake_get_draft)
    monkeypatch.setattr(main.draft_service, "update_draft", fake_update_draft)

    # Drive the background task deterministically: mark the job completed.
    def fake_generate_paper(draft, job, *, bucket):
        job.record_slot_result("q1", "A", [{"question_text": "x", "generation_model": "sonnet-4.5",
                                            "token_usage": {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2}}],
                               {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2}, [])
        return {"generatedAt": "2024-01-01T00:00:00Z",
                "token_usage": {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2, "by_model": {}},
                "sections": {}}

    def fake_persist_paper(paper, *, user_id, draft_id, bucket):
        return f"s3://{bucket}/Generated/{user_id}/{draft_id}/paper.json"

    monkeypatch.setattr(main.generation_service, "generate_paper", fake_generate_paper)
    monkeypatch.setattr(main.generation_output, "persist_paper", fake_persist_paper)

    return TestClient(main.app), updates


def test_post_generate_starts_job(client):
    tc, updates = client
    resp = tc.post("/api/generate", json={"draftId": "draft-ok"}, headers={"X-User-Id": "u1"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "generating"
    assert body["jobId"]
    # draft marked generating; background task completed it.
    job = job_store.get(body["jobId"])
    assert job is not None
    assert job.status == "completed"
    # generatedPaper pointer written.
    assert any(u[2].get("generatedPaper") for u in updates)


def test_post_generate_missing_draft_id(client):
    tc, _ = client
    resp = tc.post("/api/generate", json={"draftId": ""}, headers={"X-User-Id": "u1"})
    assert resp.status_code == 400


def test_post_generate_no_usable_question_paper(client):
    tc, _ = client
    resp = tc.post("/api/generate", json={"draftId": "draft-empty"}, headers={"X-User-Id": "u1"})
    assert resp.status_code == 400


def test_post_generate_unknown_draft(client):
    tc, _ = client
    resp = tc.post("/api/generate", json={"draftId": "nope"}, headers={"X-User-Id": "u1"})
    assert resp.status_code == 404


def test_get_status_and_foreign_job(client):
    tc, _ = client
    start = tc.post("/api/generate", json={"draftId": "draft-ok"}, headers={"X-User-Id": "u1"})
    job_id = start.json()["jobId"]

    ok = tc.get(f"/api/generate/{job_id}", headers={"X-User-Id": "u1"})
    assert ok.status_code == 200
    snap = ok.json()
    assert snap["jobId"] == job_id
    assert "progress" in snap and "token_usage" in snap

    # Foreign user cannot see it.
    foreign = tc.get(f"/api/generate/{job_id}", headers={"X-User-Id": "u2"})
    assert foreign.status_code == 404

    unknown = tc.get("/api/generate/does-not-exist", headers={"X-User-Id": "u1"})
    assert unknown.status_code == 404
