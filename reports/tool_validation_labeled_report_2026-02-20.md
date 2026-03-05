# Labeled Dataset Tool Validation (20 Feb 2026)

- Input dataset: `reports/external_ragbench_20_traces.json`
- Processed samples: **20/20** (errors=0)

## Correlation to Ground Truth Labels

- Pearson(overall, gt): **0.5855**
- Pearson(faithfulness, gt): **0.4696**
- Spearman(overall, gt): **0.5834**
- Spearman(faithfulness, gt): **0.5179**

## Binary Agreement (threshold=0.5)

- Overall -> Acc: **0.5000**, F1: **0.6667**
- Faithfulness -> Acc: **0.5500**, F1: **0.6400**

## Bucket Separation (Low vs High label)

- Mean overall (low): **0.6850**
- Mean overall (high): **0.8329**
- Mean faithfulness (low): **0.4350**
- Mean faithfulness (high): **0.7833**

## Pass/Fail Gates

- Corr gate (both >=0.4): **PASS**
- Faithfulness F1 gate (>=0.7): **FAIL**
- Bucket gap gate (overall_high-overall_low >=0.15): **FAIL**

## Output

- JSON detail: `reports/tool_validation_labeled_results_2026-02-20.json`