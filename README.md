# agent-loop-safeguard

[![CI](https://github.com/mgnlia/agent-loop-safeguard/actions/workflows/ci.yml/badge.svg)](https://github.com/mgnlia/agent-loop-safeguard/actions/workflows/ci.yml)

Agent loop safeguard library for AI agent runtimes. Addresses the three root causes of runaway loops observed at iterations 22, 43, and 29.

## Features

| Feature | Module | Default |
|---|---|---|
| Loop detection via action fingerprinting | `LoopDetector` | window=10, threshold=2 |
| Exponential backoff with jitter | `ExponentialBackoff` | base=1s, cap=60s, max_retries=8 |
| Auto-summarize context at iter 15 | `ContextSummarizer` | trigger=15, repeat_every=10 |
| Force task decomposition on escalation | `ForcePlanner` | 3-step decompose |
| Unified facade | `LoopSafeguard` | all of the above |

## Quick Start

```python
from loop_safeguard import LoopSafeguard

safeguard = LoopSafeguard()   # sensible defaults
context = []

for iteration in range(1, 100):
    action, tool, args = agent.next_action()

    # 1. Maybe auto-summarize context at iter 15, 25, 35 ...
    context = safeguard.maybe_summarize(iteration, context, task_state=current_task)

    # 2. Check for loop, apply backoff, or force re-plan
    outcome = safeguard.check_and_handle(
        iteration=iteration,
        action=action,
        tool=tool,
        args=args,
        context=context,
        task=current_task,
    )

    if outcome.force_replanned:
        # Restart with decomposed subtasks
        subtasks = outcome.replan_result.subtasks
        break

    # 3. Execute normally
    result = agent.execute(action, tool, args)
    context.append({"action": action, "tool": tool, "result": result})
```

## Architecture

```
LoopSafeguard (facade)
├── LoopDetector          — SHA-fingerprints each action; flags repeats in sliding window
├── ExponentialBackoff    — Computes jittered wait; raises LoopEscalationError at max_retries
├── ContextSummarizer     — Fires at iter 15 (and every 10 after); prunes + compresses context
└── ForcePlanner          — Decomposes task into subtasks; resets detector + backoff
```

## Configuration

```python
from loop_safeguard.safeguard import SafeguardConfig
from loop_safeguard.detector import LoopDetectorConfig
from loop_safeguard.backoff import BackoffConfig
from loop_safeguard.summarizer import SummarizerConfig

cfg = SafeguardConfig(
    detector=LoopDetectorConfig(window_size=10, repeat_threshold=2),
    backoff=BackoffConfig(base_seconds=1.0, multiplier=2.0, cap_seconds=60.0, max_retries=8),
    summarizer=SummarizerConfig(trigger_iteration=15, repeat_every=10, max_context_entries=50),
)
safeguard = LoopSafeguard(config=cfg)
```

## Custom LLM-backed Summarizer / Decomposer

```python
# Plug in your own LLM-backed summarizer
safeguard.summarizer.register_summary_fn(lambda ctx: llm.summarize(ctx))

# Plug in your own LLM-backed decomposer
safeguard.planner.register_decompose_fn(lambda task: llm.decompose(task))
```

## Install

```bash
uv pip install -e ".[dev]"
pytest
```

## License

MIT
