"""
Context Summarizer
==================
Auto-summarizes agent context at iteration 15 (configurable) to prevent
context-window bloat from driving the agent into repetitive behaviour.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

SummaryFn = Callable[[List[Dict[str, Any]]], str]


@dataclass
class SummarizerConfig:
    trigger_iteration: int = 15        # summarize at this iteration
    repeat_every: int = 10             # re-summarize every N iterations after trigger
    max_context_entries: int = 50      # prune context to this length post-summary
    include_task_state: bool = True    # include current task status in summary


def _default_summary_fn(context: List[Dict[str, Any]]) -> str:
    """
    Naive built-in summarizer — concatenates action + result digests.
    Replace with an LLM-backed summarizer in production.
    """
    lines = []
    for i, entry in enumerate(context[-20:]):  # last 20 entries
        action = entry.get("action", "?")
        result_snippet = str(entry.get("result", ""))[:80]
        lines.append(f"[{i}] {action}: {result_snippet}")
    return "CONTEXT SUMMARY (last 20 actions):\n" + "\n".join(lines)


class ContextSummarizer:
    """
    Fires at a configured iteration threshold and injects a compressed
    summary into the context, pruning older entries.

    Usage::

        summarizer = ContextSummarizer()
        new_context = summarizer.maybe_summarize(iteration=15, context=ctx)
    """

    def __init__(
        self,
        config: Optional[SummarizerConfig] = None,
        summary_fn: Optional[SummaryFn] = None,
    ) -> None:
        self.config = config or SummarizerConfig()
        self._summary_fn: SummaryFn = summary_fn or _default_summary_fn
        self._summary_history: List[Dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def should_summarize(self, iteration: int) -> bool:
        """Return True if this iteration should trigger a summary."""
        cfg = self.config
        if iteration == cfg.trigger_iteration:
            return True
        if iteration > cfg.trigger_iteration:
            return (iteration - cfg.trigger_iteration) % cfg.repeat_every == 0
        return False

    def maybe_summarize(
        self,
        iteration: int,
        context: List[Dict[str, Any]],
        task_state: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        If the trigger condition is met, produce a summary entry and
        return a pruned context list with the summary prepended.

        Parameters
        ----------
        iteration : int
            Current agent iteration counter.
        context : list
            Current context entries (each a dict with at least 'action').
        task_state : dict, optional
            Current task metadata to embed in the summary.

        Returns
        -------
        list
            Potentially pruned + summarized context.
        """
        if not self.should_summarize(iteration):
            return context

        logger.info(
            "ContextSummarizer triggered at iteration %d — compressing %d entries",
            iteration,
            len(context),
        )

        summary_text = self._summary_fn(context)

        if self.config.include_task_state and task_state:
            summary_text += f"\n\nTASK STATE @ iter {iteration}:\n"
            for k, v in task_state.items():
                summary_text += f"  {k}: {v}\n"

        summary_entry: Dict[str, Any] = {
            "action": "__context_summary__",
            "iteration": iteration,
            "summary": summary_text,
            "entries_compressed": len(context),
        }

        self._summary_history.append(summary_entry)

        # Prune and prepend summary
        pruned = context[-self.config.max_context_entries :]
        return [summary_entry] + pruned

    def register_summary_fn(self, fn: SummaryFn) -> None:
        """Swap in a custom (e.g. LLM-backed) summarizer at runtime."""
        self._summary_fn = fn
        logger.info("Custom summary function registered")

    @property
    def summary_history(self) -> List[Dict[str, Any]]:
        return list(self._summary_history)
