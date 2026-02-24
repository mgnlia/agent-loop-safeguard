"""Tests for ExponentialBackoff."""
import pytest
from loop_safeguard.backoff import BackoffConfig, ExponentialBackoff, LoopEscalationError


def test_duration_grows_exponentially():
    cfg = BackoffConfig(base_seconds=1.0, multiplier=2.0, cap_seconds=100.0, jitter=False)
    b = ExponentialBackoff(cfg)
    d0 = b.next_duration()
    b.wait(dry_run=True)
    d1 = b.next_duration()
    b.wait(dry_run=True)
    d2 = b.next_duration()
    assert d1 == pytest.approx(d0 * 2.0)
    assert d2 == pytest.approx(d0 * 4.0)


def test_cap_respected():
    cfg = BackoffConfig(base_seconds=1.0, multiplier=10.0, cap_seconds=5.0, jitter=False)
    b = ExponentialBackoff(cfg)
    for _ in range(5):
        b.wait(dry_run=True)
    assert b.next_duration() <= 5.0


def test_escalation_after_max_retries():
    cfg = BackoffConfig(max_retries=3, jitter=False)
    b = ExponentialBackoff(cfg)
    for _ in range(3):
        b.wait(dry_run=True)
    with pytest.raises(LoopEscalationError):
        b.wait(dry_run=True)


def test_reset_clears_retry_count():
    b = ExponentialBackoff(BackoffConfig(jitter=False))
    b.wait(dry_run=True)
    b.wait(dry_run=True)
    assert b.retry_count == 2
    b.reset()
    assert b.retry_count == 0
