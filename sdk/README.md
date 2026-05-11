# rageval-ai

Standalone RAG evaluation library — run LLM-as-judge evaluation locally with your own API key.

## Installation

```bash
pip install rageval-ai
```

## Quick Start

Set your API key:

```bash
export OPENAI_API_KEY="sk-your-key"
```

### Single Trace (3 lines)

```python
from rageval_sdk import evaluate

result = evaluate("What is the capital of France?", "Paris.", ["Paris is the capital of France."])
print(result["overall_score"])  # 0.95
```

### Batch Evaluation

```python
from rageval_sdk import evaluate_batch

results = evaluate_batch([
    {"question": "What is RAG?", "answer": "Retrieval-Augmented Generation.", "contexts": ["RAG combines retrieval with generation."]},
    {"question": "What is Python?", "answer": "A programming language.", "contexts": ["Python was created by Guido van Rossum."]},
])

for r in results:
    print(f"Score: {r['overall_score']}")
```

### Custom Configuration

```python
from rageval_sdk import evaluate, EvalConfig

config = EvalConfig(
    api_key="sk-...",
    base_url="https://openrouter.ai/api/v1",  # OpenAI, Azure, OpenRouter, etc.
    stage_1_model="gpt-4o",
    stage_2_model="gpt-4o-mini",
)

result = evaluate("Question?", "Answer.", ["Context."], config=config)
```

### Background Evaluation (Non-blocking)

```python
from rageval_sdk import RagEvaluator

evaluator = RagEvaluator(api_key="sk-...", max_workers=4)

for query in user_queries:
    answer, contexts = my_rag_pipeline(query)
    evaluator.submit(question=query, answer=answer, contexts=contexts)

results = evaluator.wait()
evaluator.shutdown()
```

## Evaluation Metrics

| Metric | Description |
|--------|-------------|
| `overall_score` | Weighted composite score (0-1) |
| `hallucination_score` | Detects fabricated information |
| `faithfulness` | Answer grounded in context |
| `answer_relevancy` | Answer relevance to question |
| `context_precision` | Quality of retrieved context |
| `context_recall` | Coverage of necessary information |
| `clarity` | Answer clarity |
| `coherence` | Answer coherence |
| `helpfulness` | Answer helpfulness |
| `citation_check` | Source citation validation |

## API Reference

### `evaluate(question, answer, contexts, ground_truth, *, api_key, config)`

Evaluate a single trace. Returns dict with all metrics.

- `question` (str): User question
- `answer` (str): LLM answer
- `contexts` (list[str], optional): Retrieved context passages
- `ground_truth` (str, optional): Expected answer
- `api_key` (str, optional): Auto-detected from `OPENAI_API_KEY` env
- `config` (EvalConfig, optional): Custom configuration

### `evaluate_batch(traces, *, api_key, config, max_concurrency)`

Evaluate multiple traces in parallel. Returns list of result dicts.

- `traces` (list[dict]): List of `{"question", "answer", "contexts", "ground_truth"}`
- `max_concurrency` (int): Max parallel evaluations (default 4)

### `EvalConfig`

Configuration object for custom LLM providers:

- `api_key`: API key
- `base_url`: API endpoint (default: OpenAI)
- `stage_1_model`: Reasoning model (default: gpt-4o)
- `stage_2_model`: JSON scoring model (default: gpt-4o-mini)
- `rag_metrics_model`: RAG metrics model (default: gpt-4o-mini)

## License

MIT
