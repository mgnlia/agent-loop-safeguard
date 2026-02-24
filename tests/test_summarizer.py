"""Tests for ContextSummarizer."""
from loop_safeguard.summarizer import ContextSummarizer, SummarizerConfig


def test_should_summarize_at_trigger():
    s = ContextSummarizer(SummarizerConfig(trigger_iteration=15))
    assert s.should_summarize(15)
    assert not s.should_summarize(14)
    assert not s.should_summarize(16)


def test_should_summarize_repeat_every():
    s = ContextSummarizer(SummarizerConfig(trigger_iteration=15, repeat_every=10))
    assert s.should_summarize(15)
    assert s.should_summarize(25)
    assert s.should_summarize(35)
    assert not s.should_summarize(20)


def test_maybe_summarize_prunes_context():
    ctx = [{"action": f"act_{i}", "result": "ok"} for i in range(100)]
    s = ContextSummarizer(SummarizerConfig(trigger_iteration=15, max_context_entries=20))
    new_ctx = s.maybe_summarize(15, ctx)
    # summary entry + up to 20 pruned entries
    assert len(new_ctx) <= 21
    assert new_ctx[0]["action"] == "__context_summary__"


def test_maybe_summarize_no_op_before_trigger():
    ctx = [{"action": "act", "result": "ok"}] * 5
    s = ContextSummarizer(SummarizerConfig(trigger_iteration=15))
    new_ctx = s.maybe_summarize(10, ctx)
    assert new_ctx == ctx


def test_custom_summary_fn():
    s = ContextSummarizer()
    s.register_summary_fn(lambda ctx: "CUSTOM SUMMARY")
    new_ctx = s.maybe_summarize(15, [{"action": "x", "result": "y"}])
    assert new_ctx[0]["summary"] == "CUSTOM SUMMARY"
