# Adversarial Benchmark Report

## Summary

| Metric | Value |
|--------|-------|
| Total traces | 23 |
| Completed | 23 (100%) |
| Failed | 0 |
| Stage 1 success | 23/23 (100%) |
| Score range | 0.15 – 1.0 |
| Overall avg | 0.639 |

## Scores by Scenario

| Scenario | n | Avg Score | Min | Max | Expected Range | Verdict |
|-----------|---|-----------|-----|-----|----------------|---------|
| **correct** | 8 | 0.79 | 0.52 | 1.0 | 0.7–1.0 | ✅ Mostly correct |
| **contradictory** | 2 | 0.55 | 0.48 | 0.62 | 0.0–0.3 | ⚠️ Too high |
| **hallucinated** | 5 | 0.71 | 0.5 | 1.0 | 0.0–0.4 | ❌ Much too high |
| **deflection** | 2 | 0.45 | 0.45 | 0.45 | 0.0–0.3 | ⚠️ Slightly high |
| **partial** | 2 | 0.66 | 0.55 | 0.76 | 0.3–0.6 | ⚠️ Slightly high |
| **unanswerable** | 3 | 0.30 | 0.15 | 0.54 | 0.0–0.4 | ✅ In range |
| **irrelevant_context** | 1 | 0.82 | 0.82 | 0.82 | 0.2–0.5 | ❌ Too high |

## Key Findings

### 1. Stage 1 Token Limit Bug (Fixed)
**Root cause**: `gpt-5.2` is a reasoning model that uses internal chain-of-thought tokens. The default `max_completion_tokens=512` was consumed entirely by the model's internal reasoning, leaving **zero tokens for visible output** (`finish_reason=length`, `content=""`).

**Fix**: Increased `max_completion_tokens` from 512 → 16384 for Stage 1. Also increased `openai_timeout_seconds` from 30 → 120 to accommodate reasoning model latency.

**Impact**: Stage 1 success rate went from 39% → 100%.

### 2. Score Discrimination (Improved)
Compared to previous extractive QA benchmark (all scores 0.88–1.0):
- Scores now range from **0.15 to 1.0** (wide spread)
- System correctly gives 1.0 to well-supported answers
- System correctly gives low scores to unanswerable questions
- System identifies `confirmed contradiction` and `unsupported claim` in disagreement_claims

### 3. Hallucination Detection Weakness
The biggest gap: hallucinated answers score **avg 0.71** instead of expected 0.0–0.4.

**Reason**: The evaluation rubric focuses on *answer quality* (clarity, coherence, helpfulness) rather than *factual grounding*. A well-written hallucinated answer scores high on surface quality metrics even when it contains fabricated claims. The `disagreement_claims` correctly tag contradictions/unsupported claims, but this doesn't sufficiently reduce the `overall_score`.

### 4. Contradictory Answers Score Too High
Contradictory answers (Berlin is capital of France) score 0.48-0.62. The system correctly identifies contradictions in `disagreement_claims`, but `overall_score` doesn't drop low enough.

## Recommendations

1. **Weight disagreement_claims in overall_score**: Any `confirmed contradiction` should cap overall_score at ≤ 0.3. Any `unsupported claim` / `fabricated` should reduce proportionally.

2. **Add context_relevance metric**: Missing from current rubric. Should penalize when provided context doesn't match the question.

3. **Add faithfulness / groundedness metric**: Explicit 0.0–1.0 score for how well the answer is grounded in the provided context.

4. **Adjust overall_score formula**: Currently seems to weight surface quality (clarity, coherence) equally with substance (completeness, helpfulness). Should weight substance + grounding higher.

## Data Sources

- **Amnesty QA** (`explodinggradients/amnesty_qa`): 5 samples – LLM-generated human rights Q&A
- **Neural Bridge Hallucination** (`neural-bridge/rag-hallucination-dataset-1000`): 6 samples – hallucination detection dataset
- **RAGBench** (`rungalileo/ragbench`, `hotpotqa`): 7 samples – GPT-3.5 answers with adherence scores
- **Handcrafted**: 5 samples – contradictions, deflections, partial answers, irrelevant context, hallucinations
