# All-Metrics Labeled Dataset Validation (20 Feb 2026)

- Dataset: `reports/all_metrics_labeled_dataset_2026-02-20.json`
- Total traces: **12**
- Passed: **11**
- Failed: **1**
- Pass rate: **91.67%**

## Failed checks by metric

- completeness: 1

## Per-trace Status

| # | Name | Status | Overall |
|---|---|---|---:|
| 1 | perfect_high_all | FAIL | 0.9 |
| 2 | hallucination_contradiction | PASS | 0.5725 |
| 3 | partial_answer_low_completeness | PASS | 0.8 |
| 4 | offtopic_sentence_low_relevancy | PASS | 0.775 |
| 5 | low_context_precision_noise | PASS | 0.82 |
| 6 | low_context_recall_missing_info | PASS | 0.6938 |
| 7 | deflection_case | PASS | 0.35 |
| 8 | citation_correct | PASS | 0.95 |
| 9 | citation_incorrect | PASS | 0.975 |
| 10 | clarity_low | PASS | 0.3883 |
| 11 | coherence_low_contradiction | PASS | 0.725 |
| 12 | specificity_low_vague | PASS | 0.535 |

- JSON detail: `reports/all_metrics_validation_results_2026-02-20.json`