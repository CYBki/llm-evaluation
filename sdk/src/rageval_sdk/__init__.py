"""
RAG Eval SDK — LLM evaluation library for RAG systems.

Two modes:

1. Local mode (no server needed):
    from rageval_sdk import evaluate
    result = evaluate("What is X?", "X is Y.", ["Context."])
    print(result["overall_score"])

2. Server mode (self-hosted FastAPI):
    from rageval_sdk import RagEvalClient
    client = RagEvalClient(api_url="http://your-server:8000", api_key="key")
    result = client.ingest(question="Q", answer="A", contexts=["C"])
    trace = client.get_trace(result["id"])
"""

__version__ = "0.2.1"

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
