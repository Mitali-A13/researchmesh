"""Tests for the background research jobs (no real AI, search or network)."""

import os, sys, tempfile, threading, time

_db = os.path.join(tempfile.mkdtemp(), "jobs.db")
os.environ.setdefault("MISTRAL_API_KEY", "d")
os.environ.setdefault("TAVILY_API_KEY", "d")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-pytest-1234")
os.environ.setdefault("DATABASE_URL", f"sqlite:///{_db}")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

import backend.pipeline as pipeline_mod
from backend.agents import Critique
from backend.app import app
from backend.db.database import SessionLocal
from backend.db.models import ResearchJob
from backend.services import jobs as jobs_mod

c = TestClient(app)

FAKE_OK = {
    "status": "success",
    "report": "Body [1]\n\n## Sources\n- **[1]** [A](https://a.com)",
    "feedback": "Score: 8/10",
    "sources": [{"id": 1}],
    "warnings": [],
    "error": None,
    "scores": [8],
    "revisions": 0,
    "verification": None,
}


def make_user(name):
    email = f"{name}@jobs-example.com"
    c.post("/signup", json={"name": name, "email": email, "password": "secret1"})
    token = c.post("/login", json={"email": email, "password": "secret1"}).json()[
        "access_token"
    ]
    return {"Authorization": f"Bearer {token}"}


def wait_for(job_id, headers, wanted=("completed", "failed"), timeout=10):
    end = time.time() + timeout
    while time.time() < end:
        body = c.get(f"/research/jobs/{job_id}", headers=headers).json()
        if body["job"]["status"] in wanted:
            return body
        time.sleep(0.05)
    raise AssertionError(f"job did not reach {wanted}")


def test_a_report_runs_in_the_background_and_can_be_polled():
    h = make_user("alice")
    with patch("backend.services.jobs.generate_research", return_value=FAKE_OK):
        r = c.post("/research", json={"topic": "  solid   state batteries "}, headers=h)
        assert r.status_code == 202
        job = r.json()["job"]
        assert (
            job["status"] in ("queued", "running")
            and job["topic"] == "solid state batteries"
        )
        body = wait_for(job["id"], h)
    assert body["job"]["status"] == "completed" and body["job"]["stage"] == "Done"
    assert body["data"]["report"].startswith("Body")
    assert body["job"]["history_id"] and body["job"]["finished_at"]


def test_progress_stage_is_visible_while_running():
    h = make_user("bob")
    reached, release = threading.Event(), threading.Event()

    def slow(topic, on_stage=None):
        on_stage("Writing the report")
        reached.set()
        release.wait(5)
        return FAKE_OK

    with patch("backend.services.jobs.generate_research", side_effect=slow):
        job = c.post("/research", json={"topic": "progress topic"}, headers=h).json()[
            "job"
        ]
        assert reached.wait(5)
        body = c.get(f"/research/jobs/{job['id']}", headers=h).json()
        assert (
            body["job"]["status"] == "running"
            and body["job"]["stage"] == "Writing the report"
        )
        assert "data" not in body  # no result before it is finished
        release.set()
        assert wait_for(job["id"], h)["job"]["status"] == "completed"


def test_only_the_owner_can_see_a_job_and_login_is_required():
    owner, other = make_user("carol"), make_user("dave")
    with patch("backend.services.jobs.generate_research", return_value=FAKE_OK):
        job = c.post(
            "/research", json={"topic": "private topic"}, headers=owner
        ).json()["job"]
        wait_for(job["id"], owner)
    assert c.get(f"/research/jobs/{job['id']}", headers=other).status_code == 404
    assert c.get(f"/research/jobs/{job['id']}").status_code in (401, 403)
    assert c.get("/research/jobs/doesnotexist", headers=owner).status_code == 404


def test_blank_topics_are_rejected():
    h = make_user("erin")
    for bad in ["   ", "ab", ""]:
        assert c.post("/research", json={"topic": bad}, headers=h).status_code == 422


def test_only_one_report_at_a_time_per_user():
    h = make_user("frank")
    release = threading.Event()

    def slow(topic, on_stage=None):
        release.wait(5)
        return FAKE_OK

    with patch("backend.services.jobs.generate_research", side_effect=slow):
        first = c.post("/research", json={"topic": "first topic"}, headers=h).json()[
            "job"
        ]
        second = c.post("/research", json={"topic": "second topic"}, headers=h)
        assert second.status_code == 409 and "in progress" in second.json()["detail"]
        release.set()
        wait_for(first["id"], h)
        third = c.post("/research", json={"topic": "third topic"}, headers=h)
        assert third.status_code == 202
        wait_for(third.json()["job"]["id"], h)


def test_daily_limit_counts_reports_but_not_failures(monkeypatch):
    monkeypatch.setenv("DAILY_REPORT_LIMIT", "2")
    h = make_user("gina")
    failed = {"status": "failed", "error": "No search results found for this topic."}
    with patch("backend.services.jobs.generate_research", return_value=failed):
        r = c.post("/research", json={"topic": "fails once"}, headers=h)
        assert wait_for(r.json()["job"]["id"], h)["job"]["status"] == "failed"
    with patch("backend.services.jobs.generate_research", return_value=FAKE_OK):
        for topic in ["ok topic one", "ok topic two"]:
            r = c.post("/research", json={"topic": topic}, headers=h)
            assert r.status_code == 202
            wait_for(r.json()["job"]["id"], h)
        blocked = c.post("/research", json={"topic": "ok topic three"}, headers=h)
    assert blocked.status_code == 429 and "Daily limit" in blocked.json()["detail"]


def test_a_crash_in_the_pipeline_ends_as_a_failed_job_not_a_stuck_one():
    h = make_user("hank")
    with patch(
        "backend.services.jobs.generate_research", side_effect=RuntimeError("boom")
    ):
        r = c.post("/research", json={"topic": "crash topic"}, headers=h)
        body = wait_for(r.json()["job"]["id"], h)
    assert body["job"]["status"] == "failed" and "boom" in body["job"]["error"]


def test_unfinished_jobs_are_marked_failed_after_a_restart():
    h = make_user("ivy")
    user_id = c.get("/me", headers=h).json()["user"]["id"]
    with SessionLocal() as db:
        for jid, status in [
            ("q" * 32, "queued"),
            ("r" * 32, "running"),
            ("d" * 32, "completed"),
        ]:
            db.add(ResearchJob(id=jid, user_id=user_id, topic="t", status=status))
        db.commit()
    assert jobs_mod.fail_stale_jobs() >= 2
    with SessionLocal() as db:
        assert db.get(ResearchJob, "q" * 32).status == "failed"
        assert db.get(ResearchJob, "r" * 32).status == "failed"
        assert "restarted" in db.get(ResearchJob, "r" * 32).error
        assert db.get(ResearchJob, "d" * 32).status == "completed"  # untouched


def test_deleting_a_report_does_not_break_its_job():
    h = make_user("jack")
    with patch("backend.services.jobs.generate_research", return_value=FAKE_OK):
        r = c.post("/research", json={"topic": "delete me later"}, headers=h)
        body = wait_for(r.json()["job"]["id"], h)
    assert (
        c.delete(f"/history/{body['job']['history_id']}", headers=h).status_code == 200
    )
    assert c.get(f"/research/jobs/{body['job']['id']}", headers=h).status_code == 200


# ---------- progress reporting inside the real pipeline ----------

SOURCES = [
    {
        "id": 1,
        "title": "A",
        "url": "https://a.com",
        "read": "full",
        "text": "Fact one. " * 20,
    },
    {
        "id": 2,
        "title": "B",
        "url": "https://b.com",
        "read": "full",
        "text": "Fact two. " * 20,
    },
]


class Writer:
    def invoke(self, _):
        return "## Introduction\nFact one is true and widely documented here [1]."


class Reviser:
    def invoke(self, _):
        return "## Introduction\nFact one is true and widely documented here [1][2]."


class Critic:
    def __init__(self):
        self.scores = iter([5, 9])

    def invoke(self, _):
        return Critique(
            score=next(self.scores),
            strengths=["ok"],
            improvements=["more"],
            verdict="v",
        )


def run_pipeline(on_stage):
    with (
        patch.object(pipeline_mod, "gather_sources", return_value=(SOURCES, [])),
        patch.object(pipeline_mod, "writer_chain", Writer()),
        patch.object(pipeline_mod, "reviser_chain", Reviser()),
        patch.object(pipeline_mod, "critic_chain", Critic()),
    ):
        return pipeline_mod.run_research_pipeline("topic here", on_stage=on_stage)


def test_pipeline_reports_its_stages_in_order():
    stages = []
    state = run_pipeline(stages.append)
    assert state["status"] == "success"
    assert stages == [
        pipeline_mod.STAGE_SEARCH,
        pipeline_mod.STAGE_WRITE,
        pipeline_mod.STAGE_REVIEW,
        pipeline_mod.STAGE_REVISE,
        pipeline_mod.STAGE_REVIEW,
        pipeline_mod.STAGE_VERIFY,
    ]


def test_a_broken_progress_callback_never_breaks_the_pipeline():
    def broken(stage):
        raise RuntimeError("database is down")

    assert run_pipeline(broken)["status"] == "success"
    assert run_pipeline(None)["status"] == "success"
