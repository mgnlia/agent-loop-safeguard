"""
Exponential Backoff
===================
Calculates wait durations for loop-triggered backoff with jitter,
capped at a configurable ceiling.
"""

from __future__ import annotations

import logging
import random
import time
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class BackoffConfig:
    base_seconds: float = 1.0       # initial wait
    multiplier: float = 2.0         # growth factor per retry
    cap_seconds: float = 60.0       # hard ceiling
    jitter: bool = True             # add ±25% random jitter
    max_retries: int = 8            # after this, raise LoopEscalationError


class LoopEscalationError(RuntimeError):
    """Raised when max_retries is exhausted without breaking the loop."""


class ExponentialBackoff:
    """
    Stateful exponential backoff tracker.

    Usage::

        backoff = ExponentialBackoff()
        while detector.check(...).is_loop:
            backoff.wait()          # sleeps and increments retry count
        backoff.reset()             # clear on success
    """

    def __init__(self, config: Optional[BackoffConfig] = None) -> None:
        self.config = config or BackoffConfig()
        self._retry_count: int = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def wait(self, *, dry_run: bool = False) -> float:
        """
        Sleep for the computed backoff duration and increment retry count.

        Parameters
        ----------
        dry_run:
            If True, compute and return the duration without sleeping
            (useful for testing).

        Returns
        -------
        float
            The actual duration slept (or that would be slept).

        Raises
        ------
        LoopEscalationError
            When retry count exceeds max_retries.
        """
        if self._retry_count >= self.config.max_retries:
            raise LoopEscalationError(
                f"Loop not resolved after {self.config.max_retries} retries. "
                "Escalating to force re-planning."
            )

        duration = self._compute_duration()
        logger.warning(
            "Backoff retry %d/%d — sleeping %.2fs",
            self._retry_count + 1,
            self.config.max_retries,
            duration,
        )

        if not dry_run:
            time.sleep(duration)

        self._retry_count += 1
        return duration

    def reset(self) -> None:
        """Reset retry count after successful loop break."""
        self._retry_count = 0
        logger.info("ExponentialBackoff reset")

    @property
    def retry_count(self) -> int:
        return self._retry_count

    def next_duration(self) -> float:
        """Peek at the next backoff duration without advancing state."""
        return self._compute_duration()

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _compute_duration(self) -> float:
        raw = self.config.base_seconds * (
            self.config.multiplier ** self._retry_count
        )
        capped = min(raw, self.config.cap_seconds)
        if self.config.jitter:
            jitter_factor = 1.0 + random.uniform(-0.25, 0.25)
            capped *= jitter_factor
        return round(capped, 3)
