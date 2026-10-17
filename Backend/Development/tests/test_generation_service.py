"""Tests for services.generation_service (design §3). No real Bedrock/S3/RAG."""

import pytest

from services import generation_service as gs
from services import llm_client, rag_retrieval, generation_output
from services.job_store import Job
from services.rag_retrieval import RetrievedContext, SourceChunk


# --------------------------------------------------------------------------- #
# Pure helpers
# --------------------------------------------------------------------------- #
def test_normalize_domain():
    assert gs.normalize_domain("R/U") == "R/U"
    assert gs.normalize_domain("Ap") == "AP"
    assert gs.normalize_domain("An/E") == "AN/E"
    assert gs.normalize_domain("An-E") == "AN/E"
    assert gs.normalize_domain("ane") == "AN/E"
    assert gs.normalize_domain("") == "R/U"
    assert gs.normalize_domain(None) == "R/U"
    assert gs.normalize_domain("garbage") == "R/U"


def test_route_model_from_images():
    assert gs.route_model([{"key": "d.png"}]) == "qwen-vl"
    assert gs.route_model([]) == "sonnet-4.5"
    assert gs.route_model(None) == "sonnet-4.5"


def test_slot_section_marks_wiring():
    assert gs.SLOT_SECTION == {
        "q1": "A", "q2": "A", "q3": "A", "q4": "A",
        "q5": "B", "q6": "B", "q7": "C", "q8": "D", "q9": "E",
    }
    assert gs.SLOT_MARKS == {"q1": 1, "q2": 1, "q3": 1, "q4": 1, "q5": 2, "q6": 2, "q7": 3, "q8": 5, "q9": 4}


def test_resolve_folder_prefers_draft_chapters():
    draft = {"grade": "Grade 7", "subject": "Science",
             "chapters": [{"title": "Heat", "folder": "Ch04_Heat"}]}
    assert gs.resolve_folder(draft, "Heat") == "Ch04_Heat"
    assert gs.resolve_folder(draft, "Unknown") is None


def test_is_near_duplicate():
    # Normalized-text equality (punctuation/case stripped).
    assert gs.is_near_duplicate("What is heat?", "what is heat")
    # High token overlap (Jaccard >= 0.85): same 7 words, reordered.
    assert gs.is_near_duplicate(
        "define the term specific heat capacity of water",
        "the term specific heat capacity of water define",
    )
    # Low overlap -> not a duplicate.
    assert not gs.is_near_duplicate("What is heat?", "Explain photosynthesis in plants")


def test_find_duplicates_and_reconcile():
    qs = [{"question_text": "A"}, {"question_text": "A"}, {"question_text": "B"}]
    dups = gs.find_duplicates(qs, [])
    assert "A" in dups

    first = [{"question_text": "A"}, {"question_text": "B"}]
    second = [{"question_text": "C"}, {"question_text": "D"}, {"question_text": "E"}]
    merged = gs.reconcile(first, second, [])
    texts = [q["question_text"] for q in merged]
    assert len(merged) == 5
    assert len(set(texts)) == 5


def test_split_usage_even_with_remainder_to_first():
    parts = gs.split_usage({"input_tokens": 11, "output_tokens": 7, "total_tokens": 18}, 5)
    assert len(parts) == 5
    assert sum(p["input_tokens"] for p in parts) == 11
    assert sum(p["output_tokens"] for p in parts) == 7
    assert sum(p["total_tokens"] for p in parts) == 18
    # Remainder lands on the first question.
    assert parts[0]["input_tokens"] >= parts[1]["input_tokens"]


# --------------------------------------------------------------------------- #
# End-to-end generate_paper with LLM/RAG monkeypatched
# --------------------------------------------------------------------------- #
def _make_draft():
    qp = {}
    chapters = [{"title": "Heat", "folder": "Ch04_Heat"}]
    for slot in gs.SLOT_ORDER:
        qp[slot] = {"chapter": "Heat", "domain": "R/U", "images": [], "marks": 99}
    return {"grade": "Grade 7", "subject": "Science", "examType": "PT",
            "chapters": chapters, "questionPaper": qp}


_WORDS = ["alpha", "bravo", "charlie", "delta", "echo", "foxtrot", "golf", "hotel",
          "india", "juliet", "kilo", "lima", "mike", "november", "oscar", "papa",
          "quebec", "romeo", "sierra", "tango", "uniform", "victor", "whiskey",
          "xray", "yankee", "zulu"]


def _unique_phrase(seq):
    # Build a phrase of distinct words so no two questions share enough tokens to
    # register as near-duplicates (keeps the re-ask path from firing in the stub).
    base = seq * 4
    return " ".join(_WORDS[(base + k) % len(_WORDS)] for k in range(4)) + f" {seq}"


def _mcq_batch(seqs):
    return [
        {"question_text": _unique_phrase(s), "options": ["a", "b", "c", "d"],
         "correct_answer": "a", "explanation": "because"}
        for s in seqs
    ]


def _non_mcq_batch(seqs):
    return [
        {"question_text": _unique_phrase(s), "model_answer": "ans", "marking_scheme": ["1 mark"]}
        for s in seqs
    ]


@pytest.fixture
def patched_pipeline(monkeypatch):
    # Deterministic retrieval: no titan calls, canned context.
    def fake_retrieve(grade, subject, folder, title, domain, *, bucket, top_k=8):
        ctx = RetrievedContext(
            folder=folder, domain=domain, context_text="context text",
            source_chunks=[SourceChunk("c1", "p1", 1, 5, "snippet")],
        )
        return ctx, {"input_tokens": 4, "output_tokens": 0, "total_tokens": 4}

    monkeypatch.setattr(rag_retrieval, "retrieve_context", fake_retrieve)

    call_counter = {"n": 0}
    seq_counter = {"n": 0}

    def fake_text(*, system, user, max_tokens=4000, temperature=0.7, model_id=None):
        call_counter["n"] += 1
        import json
        # Globally unique sequence numbers so no near-duplicate re-ask ever fires.
        seqs = [seq_counter["n"] + k for k in range(5)]
        seq_counter["n"] += 5
        batch = _mcq_batch(seqs) if "Multiple Choice" in user else _non_mcq_batch(seqs)
        return json.dumps(batch), {"input_tokens": 100, "output_tokens": 50, "total_tokens": 150}

    monkeypatch.setattr(llm_client, "generate_text", fake_text)
    return call_counter


def test_generate_paper_produces_45_questions(patched_pipeline):
    draft = _make_draft()
    job = Job(job_id="j", user_id="u", draft_id="d")
    paper = gs.generate_paper(draft, job, bucket="test-bucket")

    total = 0
    for letter, sdata in paper["sections"].items():
        for slot, sl in sdata["slots"].items():
            qs = sl["questions"]
            total += len(qs)
            for q in qs:
                assert q["chapter"] == "Heat"
                assert q["domain"] == "R/U"
                assert q["marks"] == gs.SLOT_MARKS[slot]  # forced, not 99
                assert q["generation_model"] == "sonnet-4.5"
                assert q["source_chunks"]
                assert q["token_usage"]["total_tokens"] >= 0
    assert total == 45


def test_generate_paper_token_rollup_by_model(patched_pipeline):
    draft = _make_draft()
    job = Job(job_id="j", user_id="u", draft_id="d")
    paper = gs.generate_paper(draft, job, bucket="test-bucket")
    usage = paper["token_usage"]
    assert "by_model" in usage
    assert "sonnet-4.5" in usage["by_model"]
    assert "titan-embed" in usage["by_model"]
    # 9 slots * 150 tokens = 1350 model tokens + titan 9*4 = 36.
    assert usage["by_model"]["sonnet-4.5"]["total_tokens"] == 9 * 150
    assert usage["total_tokens"] == 9 * 150 + 9 * 4


def test_isolated_slot_error_does_not_fail_job(monkeypatch, patched_pipeline):
    draft = _make_draft()
    # q5 chapter has no folder -> per-slot error.
    draft["questionPaper"]["q5"]["chapter"] = "Missing Chapter"

    job = Job(job_id="j", user_id="u", draft_id="d")
    paper = gs.generate_paper(draft, job, bucket="test-bucket")

    assert job.status == "generating"  # not flipped to failed by the service itself
    assert "q5" in paper["sections"]["B"]["errors"]
    # The remaining slots still produced questions.
    assert len(paper["sections"]["A"]["slots"]) == 4


def test_one_reask_max_on_duplicates(monkeypatch):
    # retrieve_context stub
    def fake_retrieve(grade, subject, folder, title, domain, *, bucket, top_k=8):
        ctx = RetrievedContext(folder=folder, domain=domain, context_text="ctx",
                               source_chunks=[SourceChunk("c1", "p1", 1, 1, "s")])
        return ctx, {"input_tokens": 1, "output_tokens": 0, "total_tokens": 1}

    monkeypatch.setattr(rag_retrieval, "retrieve_context", fake_retrieve)

    calls = {"n": 0}

    def dup_then_unique(*, system, user, max_tokens=4000, temperature=0.7, model_id=None):
        import json
        calls["n"] += 1
        if calls["n"] == 1:
            # all duplicates (identical text)
            batch = [{"question_text": "same", "options": ["a", "b", "c", "d"],
                      "correct_answer": "a", "explanation": "e"} for _ in range(5)]
        else:
            batch = [{"question_text": f"unique {i}", "options": ["a", "b", "c", "d"],
                      "correct_answer": "a", "explanation": "e"} for i in range(5)]
        return json.dumps(batch), {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15}

    monkeypatch.setattr(llm_client, "generate_text", dup_then_unique)

    draft = {"grade": "Grade 7", "subject": "Science", "examType": "PT",
             "chapters": [{"title": "Heat", "folder": "Ch04_Heat"}],
             "questionPaper": {"q1": {"chapter": "Heat", "domain": "R/U", "images": []}}}
    job = Job(job_id="j", user_id="u", draft_id="d")
    gs.generate_paper(draft, job, bucket="b")

    # Exactly 2 calls for q1 (first + one re-ask), not more.
    assert calls["n"] == 2
