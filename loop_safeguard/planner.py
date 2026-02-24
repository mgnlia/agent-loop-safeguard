"""
Force Re-Planner
================
When a loop is confirmed unresolvable via backoff, this module forces
task decomposition and re-planning instead of checkpoint restore.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

DecomposeFn = Callable[[Dict[str, Any]], List[Dict[str, Any]]]


@dataclass
class ReplanResult:
    triggered: bool
    reason: str
    subtasks: List[Dict[str, Any]] = field(default_factory=list)
    original_task: Optional[Dict[str, Any]] = None


def _default_decompose_fn(task: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Naive decomposer — splits the task description into numbered sub-steps.
    Replace with an LLM-backed decomposer in production.
    """
    description = task.get("description", task.get("title", "unknown task"))
    return [
        {
            "title": f"[Replan] Step 1: Re-assess goal for: {description[:60]}",
            "action": "clarify_goal",
        },
        {
            "title": f"[Replan] Step 2: Identify blockers for: {description[:60]}",
            "action": "identify_blockers",
        },
        {
            "title": f"[Replan] Step 3: Execute unblocked sub-path",
            "action": "execute_subpath",
        },
    ]


class ForcePlanner:
    """
    Triggers forced task decomposition when backoff is exhausted.

    Usage::

        planner = ForcePlanner()
        try:
            backoff.wait()
        except LoopEscalationError:
            result = planner.replan(task=current_task, reason="loop_escalation")
            # handle result.subtasks
    """

    def __init__(self, decompose_fn: Optional[DecomposeFn] = None) -> None:
        self._decompose_fn: DecomposeFn = decompose_fn or _default_decompose_fn
        self._replan_history: List[ReplanResult] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def replan(
        self,
        task: Dict[str, Any],
        reason: str = "loop_escalation",
        context_summary: Optional[str] = None,
    ) -> ReplanResult:
        """
        Decompose the current task into subtasks and return a ReplanResult.

        Parameters
        ----------
        task : dict
            Current task metadata.
        reason : str
            Why re-planning was triggered.
        context_summary : str, optional
            Compressed context to attach to each subtask.

        Returns
        -------
        ReplanResult
        """
        logger.warning(
            "ForcePlanner triggered — reason: %s, task: %s",
            reason,
            task.get("title", "?"),
        )

        subtasks = self._decompose_fn(task)

        if context_summary:
            for st in subtasks:
                st["context_summary"] = context_summary

        result = ReplanResult(
            triggered=True,
            reason=reason,
            subtasks=subtasks,
            original_task=task,
        )
        self._replan_history.append(result)

        logger.info(
            "ForcePlanner produced %d subtasks for task '%s'",
            len(subtasks),
            task.get("title", "?"),
        )
        return result

    def register_decompose_fn(self, fn: DecomposeFn) -> None:
        """Swap in a custom (e.g. LLM-backed) decomposer at runtime."""
        self._decompose_fn = fn
        logger.info("Custom decompose function registered")

    @property
    def replan_history(self) -> List[ReplanResult]:
        return list(self._replan_history)
