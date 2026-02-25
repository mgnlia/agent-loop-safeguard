#!/usr/bin/env python3
"""Repro script for reliability incident dJrlI9zQTDm5WWbVdZsoU.

This script provides deterministic BEFORE/AFTER evidence for suppression of
repeated `task_manage:list` loop signatures (`exact_cycle_repeat`-class behavior).
"""

from __future__ import annotations

import sys
from pathlib import Path

# Make script runnable from repo root without requiring package install.
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loop_safeguard import LoopSafeguard
from loop_safeguard.backoff import BackoffConfig
from loop_safeguard.detector import LoopDetectorConfig
from loop_safeguard.safeguard import SafeguardConfig
from loop_safeguard.summarizer import SummarizerConfig


def run_before() -> None:
    print("=== BEFORE (no safeguard) ===")
    print("signature=tool_call|task_manage|{'action': 'list'}")
    for i in range(1, 9):
        print(
            f"iter={i} action=tool_call tool=task_manage args={{'action': 'list'}} "
            "result=repeat_signature_unchecked replanned=False "
            "exact_cycle_repeat_suppressed=False"
        )
    print("note=no loop-break condition; sequence would continue until hard cap")


def run_after() -> None:
    print("\n=== AFTER (with LoopSafeguard) ===")

    cfg = SafeguardConfig(
        detector=LoopDetectorConfig(window_size=6, repeat_threshold=2),
        backoff=BackoffConfig(
            base_seconds=0.1,
            multiplier=2.0,
            cap_seconds=0.2,
            max_retries=2,
            jitter=False,
        ),
        summarizer=SummarizerConfig(trigger_iteration=15, repeat_every=10, max_context_entries=20),
    )
    safeguard = LoopSafeguard(config=cfg, dry_run=True)

    context = [
        {"action": "goal", "result": "stabilize reliability lane"},
        {"action": "trace_blob", "result": "x" * 4000},
        {"action": "debug_raw", "result": "verbose stack dump"},
    ]

    print("context_len_before", len(context))
    context = safeguard.maybe_summarize(15, context, {"task_id": "dJrlI9zQTDm5WWbVdZsoU"})
    print("context_len_after", len(context))
    print("summary_injected", bool(context and context[0].get("action") == "__context_summary__"))

    for i in range(1, 9):
        outcome = safeguard.check_and_handle(
            iteration=i,
            action="tool_call",
            tool="task_manage",
            args={"action": "list"},
            context=context,
            task={
                "title": "Investigate repeated task_manage:list loop",
                "description": "Apply loop suppression and safe terminal fallback",
            },
        )
        suppressed = outcome.backoff_applied or outcome.force_replanned
        print(
            f"iter={i} loop={outcome.loop_detected} backoff_applied={outcome.backoff_applied} "
            f"replanned={outcome.force_replanned} exact_cycle_repeat_suppressed={suppressed}"
        )
        if outcome.replan_result:
            print(
                "terminal_fallback=True reason=loop_escalation "
                f"subtasks={len(outcome.replan_result.subtasks)}"
            )

    print("loop_count", len(safeguard.detector.loop_events))
    print("replan_count", len(safeguard.planner.replan_history))


def main() -> None:
    run_before()
    run_after()


if __name__ == "__main__":
    main()
