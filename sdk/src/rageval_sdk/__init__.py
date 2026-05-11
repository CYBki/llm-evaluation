"""
RAG Eval SDK — Standalone LLM evaluation library for RAG systems.

Quick Start (3 lines — set OPENAI_API_KEY env var first):

    from rageval_sdk import evaluate
    result = evaluate("What is X?", "X is Y.", ["Context about X."])
    print(result["overall_score"])

Batch:
    from rageval_sdk import evaluate_batch
    results = evaluate_batch([
        {"question": "Q1", "answer": "A1", "contexts": ["C1"]},
        {"question": "Q2", "answer": "A2", "contexts": ["C2"]},
    ])

Advanced (custom config):
    from rageval_sdk import evaluate, EvalConfig
    config = EvalConfig(api_key="sk-...", base_url="https://openrouter.ai/api/v1")
    result = evaluate("Q?", "A.", config=config)
"""

__version__ = "0.2.0"

from rageval_sdk._config import EvalConfig
from rageval_sdk._engine import RagEvaluator
from rageval_sdk._evaluator import evaluate, evaluate_batch, evaluate_trace
from rageval_sdk.client import RagEvalClient


def __getattr__(name: str):
    """Lazy import for optional dependencies (LangChain callback)."""
    if name == "RagEvalCallback":
        from rageval_sdk.callback import RagEvalCallback

        return RagEvalCallback
    raise AttributeError(f"module 'rageval_sdk' has no attribute {name!r}")


__all__ = [
    "EvalConfig",
    "RagEvaluator",
    "evaluate",
    "evaluate_batch",
    "evaluate_trace",
    "RagEvalClient",
    "RagEvalCallback",
    "__version__",
]
