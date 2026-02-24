"""Tests for LoopDetector."""
import pytest
from loop_safeguard.detector import LoopDetector, LoopDetectorConfig


def test_no_loop_on_unique_actions():
    d = LoopDetector()
    for i, action in enumerate(["search", "browse", "write", "read", "deploy"]):
        r = d.check(iteration=i, action=action)
        assert not r.is_loop


def test_loop_detected_on_repeat():
    d = LoopDetector(LoopDetectorConfig(repeat_threshold=2, window_size=5))
    d.check(iteration=1, action="web_search", tool="web_search", args={"query": "foo"})
    r = d.check(iteration=2, action="web_search", tool="web_search", args={"query": "foo"})
    assert r.is_loop
    assert r.window_count == 2


def test_different_args_no_loop():
    d = LoopDetector(LoopDetectorConfig(repeat_threshold=2))
    r1 = d.check(iteration=1, action="web_search", args={"query": "foo"})
    r2 = d.check(iteration=2, action="web_search", args={"query": "bar"})
    assert not r1.is_loop
    assert not r2.is_loop


def test_reset_clears_state():
    d = LoopDetector(LoopDetectorConfig(repeat_threshold=2))
    d.check(iteration=1, action="web_search", args={"query": "foo"})
    d.check(iteration=2, action="web_search", args={"query": "foo"})
    d.reset()
    r = d.check(iteration=3, action="web_search", args={"query": "foo"})
    assert not r.is_loop  # window was cleared


def test_loop_events_recorded():
    d = LoopDetector(LoopDetectorConfig(repeat_threshold=2))
    d.check(iteration=1, action="act", args={})
    d.check(iteration=2, action="act", args={})
    assert len(d.loop_events) == 1
    assert d.loop_events[0].iteration == 2
