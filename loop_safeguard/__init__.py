"""
agent-loop-safeguard
====================
Loop detection, exponential backoff, auto-summarize at iter 15,
and force task decomposition/re-planning for AI agent runtimes.
"""

from .detector import LoopDetector
from .backoff import ExponentialBackoff
from .summarizer import ContextSummarizer
from .safeguard import LoopSafeguard

__all__ = ["LoopDetector", "ExponentialBackoff", "ContextSummarizer", "LoopSafeguard"]
__version__ = "1.0.0"
