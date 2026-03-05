# Trace Batch Evaluation Report (20 Feb 2026)

- Source JSON: `reports/trace_batch_results_2026-02-20.json`
- Batch size: 6 traces

## Aggregate Averages

- overall_score: **0.6522**
- faithfulness: **0.4667**
- answer_relevancy: **0.8889**
- completeness: **0.35**
- context_precision: **0.9167**
- context_recall: **0.6389**

## Per-Trace Results

| Name | Trace ID | Overall | Faithfulness | AnsRel | Completeness | CtxPrecision | CtxRecall | Helpfulness | Deflection |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| perfect_retriever_reranker | 8d6c8ff9-9f88-4f96-b0fb-eab8e005d994 | 0.9150 | 0.8000 | 1.0000 | 0.7000 | 1.0000 | 1.0000 | 1.0000 | False |
| hallucination_oomkilled | a479f0d8-1ffd-455f-bafd-e2648666abc6 | 0.3683 | 0.0000 | 0.3333 | 0.4000 | 1.0000 | 0.3333 | 0.0000 | False |
| partial_latency | 50c074bf-789a-4261-b12a-ffd5103c140b | 0.8000 | 1.0000 | 1.0000 | 0.1667 | 1.0000 | 1.0000 | 0.4000 | False |
| low_context_precision | b3357b84-cb1b-4f7b-a5e9-32a05c49e33e | 0.7800 | 1.0000 | 1.0000 | 0.3333 | 0.5000 | 1.0000 | 0.7000 | False |
| low_context_recall | 21448fab-2879-4966-855b-44cf70edfa0c | 0.5350 | 0.0000 | 1.0000 | 0.4000 | 1.0000 | 0.0000 | 0.4000 | False |
| deflection_redis | 2592cbea-fcec-4219-bcf9-43a8be4e7606 | 0.5150 | 0.0000 | 1.0000 | 0.1000 | 1.0000 | 0.5000 | 0.0000 | True |

## Evaluation

- **Grounding quality is mixed**: faithfulness average is moderate (0.4667) and drops to 0.0 in hallucination/deflection-style traces.
- **Retrieval relevance is strong**: context_precision average is high (0.9167), and several traces score 1.0.
- **Retrieval coverage needs work**: context_recall average is 0.6389; low-recall scenarios are correctly penalized.
- **Answer topicality is strong**: answer_relevancy average is high (0.8889), but this alone does not guarantee factual grounding.
- **Completeness is the main weakness**: average 0.35 indicates many answers are short/partial even when relevant.

## Recommended Next Actions

1. Add stricter generation instruction: answer only from contexts; refuse unsupported claims.
2. Add completeness-oriented prompting: require multi-point coverage for process questions.
3. Keep retrieval precision as-is, improve recall with broader top-k / query rewriting.
4. Track a weekly KPI set: overall, faithfulness, completeness, context_recall.