# rageval-ai

Standalone RAG evaluation library — evaluate your RAG/LLM outputs with LLM-as-judge methodology.

**Two modes:**
- **Local mode** — No server needed, runs evaluation locally with your API key
- **Server mode** — Deploy FastAPI server, send traces from anywhere

## Installation

```bash
pip install rageval-ai
```

---

## Mode 1: Local Evaluation (No Server)

Set your API key once:

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

### Custom Provider (OpenRouter, Azure, etc.)

```python
from rageval_sdk import evaluate, EvalConfig

config = EvalConfig(
    api_key="sk-or-...",
    base_url="https://openrouter.ai/api/v1",
    stage_1_model="qwen/qwen3-235b-a22b-2507",
    stage_2_model="qwen/qwen3-32b",
)

result = evaluate("Question?", "Answer.", ["Context."], config=config)
```

---

## Mode 2: Self-Hosted Server

Deploy the FastAPI evaluation server on your own infrastructure, then send traces from any client.

### 1. Deploy Server

```bash
git clone https://github.com/CYBki/llm-evaluation.git
cd llm-evaluation

# Configure
cp .env.example .env
nano .env  # set your OPENAI_API_KEY and other settings

# Start
docker compose up -d

# Verify
curl http://localhost:8000/health
```

### 2. Send Traces via SDK

```python
from rageval_sdk import RagEvalClient

client = RagEvalClient(
    api_url="http://your-server:8000",
    api_key="your-api-key",
)

# Submit trace for evaluation
result = client.ingest(
    question="What is the capital of France?",
    answer="The capital of France is Paris.",
    contexts=["Paris is the capital and largest city of France."],
)

# Get evaluation results
trace = client.get_trace(result["id"])
print(trace["evaluation"]["overall_score"])
```

### 3. Auto-Evaluate in Your RAG Pipeline

```python
from rageval_sdk import RagEvalClient

client = RagEvalClient(api_url="http://your-server:8000", api_key="key")

def handle_query(query):
    answer, contexts = my_rag_pipeline(query)  # your existing code

    # Non-blocking: sends to server for background evaluation
    client.ingest(question=query, answer=answer, contexts=contexts)

    return answer  # user gets answer immediately
```

### 4. Webhook Notifications

```python
client.ingest(
    question="Q",
    answer="A",
    contexts=["C"],
    webhook_url="https://your-app.com/webhook",  # results POSTed here when ready
)
```

---

## Background Evaluation (Local, Non-blocking)

```python
from rageval_sdk import RagEvaluator

evaluator = RagEvaluator(api_key="sk-...", max_workers=4)

for query in user_queries:
    answer, contexts = my_rag_pipeline(query)
    evaluator.submit(question=query, answer=answer, contexts=contexts)

results = evaluator.wait()
evaluator.shutdown()
```

---

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
| `completeness` | Answer completeness |
| `citation_check` | Source citation validation |

---

## API Reference

### Local Mode

| Function | Description |
|----------|-------------|
| `evaluate(question, answer, contexts)` | Evaluate single trace (sync) |
| `evaluate_batch(traces)` | Evaluate multiple traces in parallel |
| `evaluate_trace(question, answer, contexts, config=)` | Async version |
| `RagEvaluator(max_workers=4)` | Background evaluator |
| `EvalConfig(api_key=, base_url=, ...)` | Custom configuration |

### Server Mode

| Method | Description |
|--------|-------------|
| `RagEvalClient(api_url, api_key)` | Connect to server |
| `client.ingest(question, answer, contexts)` | Submit trace |
| `client.get_trace(trace_id)` | Get results |
| `client.list_traces(limit, offset)` | List all traces |
| `client.health()` | Check server health |

---

## License

MIT
