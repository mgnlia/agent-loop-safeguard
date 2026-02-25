#!/usr/bin/env python3
"""Repro script for reliability incident nQgQmIy8Bnjak3GIR5DNN.

Shows BEFORE (no safeguard) repetitive tool loop behavior and AFTER
(loop suppression via LoopSafeguard with summarize+backoff+forced re-plan).
"""

from __future__ import annotations

from loop_safeguard import LoopSafeguard


def run_before() -> None:
    print("=== BEFORE (no safeguard) ===")
    for i in range(1, 9):
        print(
            f"iter={i} action=tool_call tool=task_manage args={{'action': 'list'}} "
            "result=repeat_signature_unchecked"
        )
    print("note=no loop-break condition; sequence would continue until hard cap")


def run_after() -> None:
    print("\n=== AFTER (with LoopSafeguard) ===")
    safeguard = LoopSafeguard(
        detector_window=6,
        detector_threshold=3,
        backoff_base_s=0.1,
        backoff_cap_s=0.2,
        backoff_max_retries=2,
        sleep_on_backoff=False,
    )

    context = {
        "goal": "stabilize reliability lane",
        "trace_blob": "x" * 4000,
        "debug_raw": "verbose stack dump",
    }
    print("context_keys_before", sorted(context.keys()))
    context = safeguard.maybe_summarize(15, context, {"task_id": "nQgQmIy8Bnjak3GIR5DNN"})
    print("context_keys_after", sorted(context.keys()))
    print("summarized", context.get("__summarized__", False))

    for i in range(1, 9):
        outcome = safeguard.check_and_handle(
            iteration=i,
            action="tool_call",
            tool="task_manage",
            args={"action": "list"},
            context=context,
            task=(
                "Investigate repeated task_manage:list loop; "
                "apply loop suppression and safe fallback"
            ),
        )
        print(
            f"iter={i} loop={outcome.loop_detected} backoff={outcome.backoff_delay_s:.3f} "
            f"replanned={outcome.force_replanned} escalated={outcome.escalated}"
        )
        if outcome.replan_result:
            print("subtasks", len(outcome.replan_result.subtasks), outcome.replan_result.subtasks)

    print("loop_count", safeguard.loop_count)
    print("replan_count", safeguard.replan_count)


def main() -> None:
    run_before()
    run_after()


if __name__ == "__main__":
    main()
