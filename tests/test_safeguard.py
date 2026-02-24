"""Integration tests for LoopSafeguard facade."""
import pytest
from loop_safeguard import LoopSafeguard
from loop_safeguard.backoff import BackoffConfig
from loop_safeguard.detector import LoopDetectorConfig
from loop_safeguard.safeguard import SafeguardConfig
from loop_safeguard.summarizer import SummarizerConfig


def make_safeguard(max_retries=2):
    cfg = SafeguardConfig(
        detector=LoopDetectorConfig(repeat_threshold=2, window_size=5),
        backoff=BackoffConfig(max_retries=max_retries, jitter=False),
        summarizer=SummarizerConfig(trigger_iteration=15),
    )
    return LoopSafeguard(config=cfg, dry_run=True)


def test_no_loop_clean_pass():
    sg = make_safeguard()
    for i, action in enumerate(["a", "b", "c", "d"]):
        outcome = sg.check_and_handle(iteration=i, action=action)
        assert not outcome.loop_detected


def test_loop_triggers_backoff():
    sg = make_safeguard(max_retries=3)
    sg.check_and_handle(iteration=1, action="search", args={"q": "x"})
    outcome = sg.check_and_handle(iteration=2, action="search", args={"q": "x"})
    assert outcome.loop_detected
    assert outcome.backoff_applied
    assert not outcome.force_replanned


def test_loop_exhaustion_triggers_replan():
    """
    With max_retries=1:
    - iter 1: first occurrence, no loop
    - iter 2: repeat → loop detected, backoff retry 1 consumed
    - iter 3: repeat → loop detected, backoff exhausted → force replan fires HERE
    After replan, detector is reset so iter 4 is clean again.
    """
    sg = make_safeguard(max_retries=1)

    sg.check_and_handle(iteration=1, action="search", args={"q": "x"})  # no loop
    sg.check_and_handle(iteration=2, action="search", args={"q": "x"})  # loop → backoff (retry 1)
    outcome = sg.check_and_handle(iteration=3, action="search", args={"q": "x"})  # escalation → replan

    assert outcome.force_replanned
    assert outcome.replan_result is not None
    assert len(outcome.replan_result.subtasks) > 0

    # After replan, detector is reset — next call is clean
    clean = sg.check_and_handle(iteration=4, action="search", args={"q": "x"})
    assert not clean.force_replanned
    assert not clean.loop_detected


def test_summarize_at_iter_15():
    sg = make_safeguard()
    ctx = [{"action": f"act_{i}", "result": "ok"} for i in range(20)]
    new_ctx = sg.maybe_summarize(15, ctx)
    assert new_ctx[0]["action"] == "__context_summary__"
