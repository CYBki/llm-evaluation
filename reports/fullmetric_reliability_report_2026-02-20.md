# Full-Metric Reliability Validation (20 Feb 2026)

- Dataset: `reports/all_metrics_fulltrace_dataset_2026-02-20.json`
- Repeats per trace: **3**
- Total traces: **9**
- Fully stable pass traces (all repeats pass): **4/9**
- Average pass rate: **59.26%**
- Final verdict: **FAIL**

## Stability by Metric (mean stddev across traces)

| Metric | Mean StdDev | Max StdDev |
|---|---:|---:|
| clarity | 0.0471 | 0.1414 |
| coherence | 0.0629 | 0.1414 |
| helpfulness | 0.0000 | 0.0000 |
| completeness | 0.0730 | 0.2079 |
| answer_relevancy | 0.0000 | 0.0000 |
| faithfulness | 0.0540 | 0.2500 |
| context_precision | 0.0000 | 0.0000 |
| context_recall | 0.0000 | 0.0000 |
| hallucination_score | 0.0540 | 0.2500 |
| citation_check | 0.1048 | 0.4714 |

## Gates

- Avg pass rate >= 0.85: **FAIL**
- Full pass ratio >= 0.70: **FAIL**
- Mean metric stddev <= 0.12: **PASS**

## Per-trace

| # | Name | Passes | Pass Rate | Overall StdDev |
|---|---|---:|---:|---:|
| 1 | perfect_grounded_with_valid_citation | 3/3 | 100.00% | 0.0312 |
| 2 | contradiction_with_wrong_citation | 3/3 | 100.00% | 0.0122 |
| 3 | partial_but_grounded | 3/3 | 100.00% | 0.0024 |
| 4 | noisy_context_low_precision | 0/3 | 0.00% | 0.0071 |
| 5 | missing_info_low_recall | 2/3 | 66.67% | 0.0260 |
| 6 | deflection | 0/3 | 0.00% | 0.0375 |
| 7 | bad_clarity_and_coherence | 2/3 | 66.67% | 0.0236 |
| 8 | vague_specificity_low | 0/3 | 0.00% | 0.0419 |
| 9 | offtopic_answer | 3/3 | 100.00% | 0.0118 |

- JSON detail: `reports/fullmetric_reliability_results_2026-02-20.json`