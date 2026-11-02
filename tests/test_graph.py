import os, sys

os.environ.setdefault("MISTRAL_API_KEY", "dummy")
os.environ.setdefault("TAVILY_API_KEY", "dummy")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.agents import Critique
from backend.graph import build_graph, run_graph


def critique(score):
    return Critique(
        score=score,
        strengths=["clear"],
        improvements=[f"fix after {score}"],
        verdict="ok",
    )


class Writer:
    def __init__(self):
        self.calls = 0

    def invoke(self, _):
        self.calls += 1
        return "draft-0"


class Reviser:
    def __init__(self, fail_on=None):
        self.calls, self.fail_on, self.feedback_seen = 0, fail_on, []

    def invoke(self, x):
        self.calls += 1
        self.feedback_seen.append(x["feedback"])
        if self.fail_on == self.calls:
            raise RuntimeError("429 rate limit")
        return f"draft-{self.calls}"


class Critic:
    """Returns the given scores one by one; an Exception item is raised instead."""

    def __init__(self, scores):
        self.scores, self.calls = list(scores), 0

    def invoke(self, _):
        item = self.scores[self.calls]
        self.calls += 1
        if isinstance(item, Exception):
            raise item
        return critique(item)


def run(scores, fail_reviser_on=None, **kwargs):
    writer, reviser, critic = Writer(), Reviser(fail_reviser_on), Critic(scores)
    app = build_graph(writer, reviser, critic, **kwargs)
    result = run_graph(app, "topic", "[1] src", "## Sources")
    return result, writer, reviser, critic


def test_improves_until_target_is_reached():
    result, writer, reviser, critic = run([5, 7, 9], target_score=8, max_revisions=2)
    assert writer.calls == 1 and reviser.calls == 2 and critic.calls == 3
    assert result["scores"] == [5, 7, 9] and result["revisions"] == 2
    assert result["best_draft"] == "draft-2" and result["best_score"] == 9
    assert (
        "fix after 5" in reviser.feedback_seen[0]
    )  # critic feedback reaches the reviser
    assert "fix after 7" in reviser.feedback_seen[1]


def test_good_first_draft_is_not_revised():
    result, _, reviser, critic = run([9], target_score=8, max_revisions=2)
    assert reviser.calls == 0 and critic.calls == 1
    assert result["scores"] == [9] and result["best_draft"] == "draft-0"


def test_stops_at_max_revisions():
    result, _, reviser, critic = run([4, 5, 5, 6, 6], target_score=8, max_revisions=2)
    assert reviser.calls == 2 and critic.calls == 3  # never loops forever
    assert result["scores"] == [4, 5, 5] and result["best_score"] == 5


def test_zero_revisions_means_write_once_and_critique_once():
    result, _, reviser, critic = run([3], target_score=8, max_revisions=0)
    assert reviser.calls == 0 and critic.calls == 1 and result["scores"] == [3]


def test_a_worse_revision_never_replaces_a_better_draft():
    result, _, _, _ = run([7, 5, 6], target_score=9, max_revisions=2)
    assert result["scores"] == [7, 5, 6]
    assert result["best_draft"] == "draft-0" and result["best_score"] == 7


def test_critic_failure_keeps_the_draft_and_stops():
    result, _, reviser, _ = run([RuntimeError("bad json")], max_revisions=2)
    assert reviser.calls == 0 and result["draft"] == "draft-0"
    assert result["scores"] == [] and result.get("best_draft") is None
    assert any("critic could not review" in n for n in result["notes"])


def test_reviser_failure_keeps_the_best_draft():
    result, _, reviser, critic = run(
        [5, 9], fail_reviser_on=1, target_score=8, max_revisions=2
    )
    assert reviser.calls == 1 and critic.calls == 1  # stopped, did not crash
    assert result["best_draft"] == "draft-0" and result["scores"] == [5]
    assert any("Revision 1 failed" in n for n in result["notes"])


def test_critic_returning_plain_text_does_not_crash():
    class TextCritic:
        def invoke(self, _):
            return "Score: 4/10"  # an old-style critic that returns text

    app = build_graph(
        Writer(), Reviser(), TextCritic(), target_score=8, max_revisions=2
    )
    result = run_graph(app, "topic", "[1] src", "## Sources")
    assert result["draft"] == "draft-0" and result["scores"] == []
    assert any("critic could not review" in n for n in result["notes"])
