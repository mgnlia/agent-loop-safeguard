"""
Loop Detector
=============
Detects repetitive agent behaviour by hashing recent action fingerprints
and flagging when the same fingerprint recurs within a sliding window.
"""

from __future__ import annotations

import hashlib
import logging
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Deque, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class LoopEvent:
    iteration: int
    fingerprint: str
    action: str
    repeated_count: int


@dataclass
class LoopDetectorConfig:
    window_size: int = 10          # how many recent actions to keep
    repeat_threshold: int = 2      # how many repeats before flagging
    hash_fields: List[str] = field(default_factory=lambda: ["action", "tool", "args_digest"])


class LoopDetector:
    """
    Detects loops by tracking action fingerprints over a sliding window.

    Usage::

        detector = LoopDetector()
        result = detector.check(iteration=1, action="web_search", tool="web_search",
                                args={"query": "foo"})
        if result.is_loop:
            ...
    """

    def __init__(self, config: Optional[LoopDetectorConfig] = None) -> None:
        self.config = config or LoopDetectorConfig()
        self._window: Deque[str] = deque(maxlen=self.config.window_size)
        self._fingerprint_counts: Dict[str, int] = {}
        self._loop_events: List[LoopEvent] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def check(
        self,
        iteration: int,
        action: str,
        tool: str = "",
        args: Optional[Dict[str, Any]] = None,
    ) -> "CheckResult":
        fingerprint = self._make_fingerprint(action, tool, args or {})
        self._window.append(fingerprint)
        self._fingerprint_counts[fingerprint] = (
            self._fingerprint_counts.get(fingerprint, 0) + 1
        )

        window_count = sum(1 for f in self._window if f == fingerprint)
        is_loop = window_count >= self.config.repeat_threshold

        if is_loop:
            event = LoopEvent(
                iteration=iteration,
                fingerprint=fingerprint,
                action=action,
                repeated_count=window_count,
            )
            self._loop_events.append(event)
            logger.warning(
                "Loop detected at iteration %d — action '%s' seen %d times in window",
                iteration,
                action,
                window_count,
            )

        return CheckResult(
            is_loop=is_loop,
            fingerprint=fingerprint,
            window_count=window_count,
            total_count=self._fingerprint_counts[fingerprint],
        )

    def reset(self) -> None:
        """Clear state — call after successful re-planning."""
        self._window.clear()
        self._fingerprint_counts.clear()
        logger.info("LoopDetector state reset")

    @property
    def loop_events(self) -> List[LoopEvent]:
        return list(self._loop_events)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _make_fingerprint(
        self, action: str, tool: str, args: Dict[str, Any]
    ) -> str:
        args_digest = hashlib.sha256(
            str(sorted(args.items())).encode()
        ).hexdigest()[:12]
        raw = f"{action}|{tool}|{args_digest}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]


@dataclass
class CheckResult:
    is_loop: bool
    fingerprint: str
    window_count: int
    total_count: int
