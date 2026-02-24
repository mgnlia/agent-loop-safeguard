"""
LoopSafeguard — Unified Facade
==============================
Single entry-point that wires together LoopDetector, ExponentialBackoff,
ContextSummarizer, and ForcePlanner into one cohesive safeguard layer.

Typical integration::

    from loop_safeguard import LoopSafeguard

    safeguard = LoopSafeguard()

    for iteration in range(1, MAX_ITER + 1):
        action, tool, args = agent.next_action()

        # 1. Maybe summarize context
        context = safeguard.maybe_summarize(iteration, context, task_state)

        # 2. Check for loop
        outcome = safeguard.check_and_handle(
            iteration=iteration,
            action=action,
            tool=tool,
            args=args,
            context=context,
            task=current_task,
        )

        if outcome.force_replanned:
            # Restart loop with decomposed subtasks
            break

        # 3. Execute action normally
        result = agent.execute(action, tool, args)
        context.append({"action": action, "tool": tool, "result": result})
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .backoff import BackoffConfig, ExponentialBackoff, LoopEscalationError
from .detector import CheckResult, LoopDetector, LoopDetectorConfig
from .planner import ForcePlanner, ReplanResult
from .summarizer import ContextSummarizer, SummarizerConfig

logger = logging.getLogger(__name__)


@dataclass
class SafeguardConfig:
    detector: LoopDetectorConfig = field(default_factory=LoopDetectorConfig)
    backoff: BackoffConfig = field(default_factory=BackoffConfig)
    summarizer: SummarizerConfig = field(default_factory=SummarizerConfig)


@dataclass
class SafeguardOutcome:
    iteration: int
    loop_detected: bool
    backoff_applied: bool
    summarized: bool
    force_replanned: bool
    replan_result: Optional[ReplanResult] = None
    check_result: Optional[CheckResult] = None
    context: List[Dict[str, Any]] = field(default_factory=list)


class LoopSafeguard:
    """
    Unified facade for all loop-safeguard subsystems.

    Parameters
    ----------
    config : SafeguardConfig, optional
        Consolidated configuration for all subsystems.
    dry_run : bool
        If True, backoff sleeps are skipped (useful for testing).
    """

    def __init__(
        self,
        config: Optional[SafeguardConfig] = None,
        dry_run: bool = False,
    ) -> None:
        cfg = config or SafeguardConfig()
        self._detector = LoopDetector(cfg.detector)
        self._backoff = ExponentialBackoff(cfg.backoff)
        self._summarizer = ContextSummarizer(cfg.summarizer)
        self._planner = ForcePlanner()
        self._dry_run = dry_run

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def maybe_summarize(
        self,
        iteration: int,
        context: List[Dict[str, Any]],
        task_state: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Run context summarization check; returns (possibly pruned) context."""
        return self._summarizer.maybe_summarize(iteration, context, task_state)

    def check_and_handle(
        self,
        iteration: int,
        action: str,
        tool: str = "",
        args: Optional[Dict[str, Any]] = None,
        context: Optional[List[Dict[str, Any]]] = None,
        task: Optional[Dict[str, Any]] = None,
    ) -> SafeguardOutcome:
        """
        Full safeguard pipeline for a single agent step:

        1. Detect loop via fingerprint comparison.
        2. If loop: apply exponential backoff.
        3. If backoff exhausted: force re-plan.

        Returns a SafeguardOutcome describing what happened.
        """
        context = context or []
        args = args or {}

        outcome = SafeguardOutcome(
            iteration=iteration,
            loop_detected=False,
            backoff_applied=False,
            summarized=False,
            force_replanned=False,
            context=context,
        )

        check = self._detector.check(iteration=iteration, action=action, tool=tool, args=args)
        outcome.check_result = check

        if not check.is_loop:
            self._backoff.reset()
            return outcome

        # Loop confirmed
        outcome.loop_detected = True
        logger.warning(
            "LoopSafeguard: loop at iter %d (fingerprint=%s, window_count=%d)",
            iteration,
            check.fingerprint,
            check.window_count,
        )

        try:
            self._backoff.wait(dry_run=self._dry_run)
            outcome.backoff_applied = True
        except LoopEscalationError as exc:
            logger.error("LoopSafeguard: backoff exhausted — forcing re-plan. %s", exc)
            context_summary = None
            if self._summarizer.summary_history:
                context_summary = self._summarizer.summary_history[-1].get("summary")

            replan = self._planner.replan(
                task=task or {},
                reason="loop_escalation",
                context_summary=context_summary,
            )
            outcome.force_replanned = True
            outcome.replan_result = replan
            # Reset detector so fresh subtasks start clean
            self._detector.reset()
            self._backoff.reset()

        return outcome

    # ------------------------------------------------------------------
    # Accessors (for observability / testing)
    # ------------------------------------------------------------------

    @property
    def detector(self) -> LoopDetector:
        return self._detector

    @property
    def backoff(self) -> ExponentialBackoff:
        return self._backoff

    @property
    def summarizer(self) -> ContextSummarizer:
        return self._summarizer

    @property
    def planner(self) -> ForcePlanner:
        return self._planner
