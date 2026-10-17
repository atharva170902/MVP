"""Tests for services.job_store (design §5)."""

import threading

from services.job_store import JobStore, Job


def _usage(i, o):
    return {"input_tokens": i, "output_tokens": o, "total_tokens": i + o}


def test_create_and_get():
    store = JobStore()
    job = store.create("user-1", "draft-1")
    assert job.job_id
    assert job.status == "generating"
    assert store.get(job.job_id) is job
    assert store.get("nope") is None


def test_record_slot_result_and_error_in_snapshot():
    job = Job(job_id="j", user_id="u", draft_id="d")
    job.record_slot_result("q1", "A", [{"question_text": "x"}], _usage(10, 5), [{"chunk_id": "c1"}])
    job.record_slot_error("q2", "chapter X could not be resolved")

    snap = job.snapshot()
    assert snap["status"] == "generating"
    assert snap["progress"]["A"] == {"done": 1, "total": 4}
    assert "q1" in snap["questions"]["A"]
    assert snap["errors"]["q2"] == "chapter X could not be resolved"
    assert snap["token_usage"] == _usage(10, 5)


def test_snapshot_section_totals():
    job = Job(job_id="j", user_id="u", draft_id="d")
    snap = job.snapshot()
    assert snap["progress"]["A"]["total"] == 4
    assert snap["progress"]["B"]["total"] == 2
    assert snap["progress"]["C"]["total"] == 1
    assert snap["progress"]["D"]["total"] == 1
    assert snap["progress"]["E"]["total"] == 1


def test_titan_usage_rolls_into_total():
    job = Job(job_id="j", user_id="u", draft_id="d")
    job.record_slot_result("q1", "A", [{"question_text": "x"}], _usage(10, 5), [])
    job.add_titan_usage(_usage(3, 0))
    snap = job.snapshot()
    assert snap["titan_usage"] == _usage(3, 0)
    assert snap["token_usage"] == _usage(13, 5)


def test_warnings_surface_in_snapshot():
    job = Job(job_id="j", user_id="u", draft_id="d")
    job.record_slot_result("q7", "C", [{"question_text": "x"}], _usage(1, 1), [], warnings=["residual near-duplicates after one re-ask"])
    snap = job.snapshot()
    assert snap["warnings"]["q7"] == ["residual near-duplicates after one re-ask"]


def test_thread_safe_totals_under_hammering():
    job = Job(job_id="j", user_id="u", draft_id="d")
    n_threads = 20
    per_thread = 50

    def worker():
        for _ in range(per_thread):
            job.add_titan_usage(_usage(1, 1))

    threads = [threading.Thread(target=worker) for _ in range(n_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    expected = n_threads * per_thread
    assert job.titan_usage == _usage(expected, expected)
