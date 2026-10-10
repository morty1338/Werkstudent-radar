# Skill extraction: sentence embeddings vs. rules

Model: `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` via fastembed (ONNX, CPU). Loading took 1 s, scoring 100 postings 68 s (684 ms per posting).

Ground truth: the 100 labelled postings in `data/eval/` (14 skills; labels made by an AI assistant, see [LABELS.md](../data/eval/LABELS.md)). Embedding thresholds were picked by 5-fold cross-validation over postings (chosen per fold: 0.63, 0.63, 0.63, 0.63, 0.63); the best single threshold on all postings would be 0.63 (micro F1 75%, optimistic).

Caveat in the rules' favour: the rules were improved after looking at disagreements on these same postings ([report_baseline.md](../data/eval/report_baseline.md) has their earlier, honest score on the random sample: micro F1 97%, vs. 98% now). The embeddings saw none of the labels except through the threshold.

## All 100 postings

| Skill | In postings | Rules P / R / F1 | Embeddings P / R / F1 | Rules ∪ emb. P / R / F1 | Rules ∩ emb. P / R / F1 |
|---|---|---|---|---|---|
| MS Office | 39 | 98% / 100% / 99% | 92% / 90% / 91% | 91% / 100% / 95% | 100% / 90% / 95% |
| Excel | 15 | 100% / 100% / 100% | 100% / 87% / 93% | 100% / 100% / 100% | 100% / 87% / 93% |
| PowerPoint | 8 | 100% / 100% / 100% | 100% / 12% / 22% | 100% / 100% / 100% | 100% / 12% / 22% |
| SAP (any) | 11 | 79% / 100% / 88% | 75% / 82% / 78% | 79% / 100% / 88% | 75% / 82% / 78% |
| SQL | 2 | 67% / 100% / 80% | 67% / 100% / 80% | 67% / 100% / 80% | 67% / 100% / 80% |
| Python | 10 | 100% / 100% / 100% | 100% / 50% / 67% | 100% / 100% / 100% | 100% / 50% / 67% |
| Java | 4 | 100% / 100% / 100% | – / 0% / 0% | 100% / 100% / 100% | – / 0% / 0% |
| JavaScript | 2 | 100% / 100% / 100% | 0% / 0% / 0% | 67% / 100% / 80% | – / 0% / 0% |
| Power BI | 2 | 100% / 100% / 100% | 100% / 50% / 67% | 100% / 100% / 100% | 100% / 50% / 67% |
| Git | 3 | 75% / 100% / 86% | 75% / 100% / 86% | 60% / 100% / 75% | 100% / 100% / 100% |
| Controlling / Reporting | 5 | 80% / 80% / 80% | 40% / 80% / 53% | 42% / 100% / 59% | 100% / 60% / 75% |
| Accounting / Buchhaltung | 5 | 100% / 80% / 89% | 38% / 60% / 46% | 50% / 100% / 67% | 100% / 40% / 57% |
| Social media | 3 | 100% / 33% / 50% | 100% / 67% / 80% | 100% / 67% / 80% | 100% / 33% / 50% |
| Driving licence (B) | 9 | 100% / 89% / 94% | 100% / 44% / 62% | 100% / 100% / 100% | 100% / 33% / 50% |
| **All 14 (micro)** | 118 | **94% / 96% / 95%** | **80% / 69% / 75%** | **84% / 99% / 91%** | **95% / 66% / 78%** |

## Random sample (70 postings, comparable with data/eval/report.md)

| Skill | In postings | Rules P / R / F1 | Embeddings P / R / F1 | Rules ∪ emb. P / R / F1 | Rules ∩ emb. P / R / F1 |
|---|---|---|---|---|---|
| MS Office | 28 | 97% / 100% / 98% | 96% / 89% / 93% | 93% / 100% / 97% | 100% / 89% / 94% |
| Excel | 8 | 100% / 100% / 100% | 100% / 88% / 93% | 100% / 100% / 100% | 100% / 88% / 93% |
| PowerPoint | 5 | 100% / 100% / 100% | – / 0% / 0% | 100% / 100% / 100% | – / 0% / 0% |
| SAP (any) | 7 | 100% / 100% / 100% | 100% / 86% / 92% | 100% / 100% / 100% | 100% / 86% / 92% |
| SQL | 2 | 100% / 100% / 100% | 100% / 100% / 100% | 100% / 100% / 100% | 100% / 100% / 100% |
| Python | 5 | 100% / 100% / 100% | 100% / 80% / 89% | 100% / 100% / 100% | 100% / 80% / 89% |
| Java | 0 | – / – / – | – / – / – | – / – / – | – / – / – |
| JavaScript | 0 | – / – / – | – / – / – | – / – / – | – / – / – |
| Power BI | 1 | 100% / 100% / 100% | 100% / 100% / 100% | 100% / 100% / 100% | 100% / 100% / 100% |
| Git | 1 | 100% / 100% / 100% | 50% / 100% / 67% | 50% / 100% / 67% | 100% / 100% / 100% |
| Controlling / Reporting | 4 | 100% / 75% / 86% | 60% / 75% / 67% | 67% / 100% / 80% | 100% / 50% / 67% |
| Accounting / Buchhaltung | 2 | 100% / 50% / 67% | 20% / 50% / 29% | 33% / 100% / 50% | – / 0% / 0% |
| Social media | 1 | 100% / 100% / 100% | 100% / 100% / 100% | 100% / 100% / 100% | 100% / 100% / 100% |
| Driving licence (B) | 5 | 100% / 100% / 100% | 100% / 20% / 33% | 100% / 100% / 100% | 100% / 20% / 33% |
| **All 14 (micro)** | 69 | **99% / 97% / 98%** | **87% / 75% / 81%** | **88% / 100% / 94%** | **100% / 72% / 84%** |

## Where the embeddings go wrong

Reference numbers and similarity scores only (job texts are not published). “Rules” says whether the rules got that case right.

| Error | Skill | Posting | Similarity | Rules right? |
|---|---|---|---|---|
| false positive | SAP (any) | 11070-1608471-1-S | 0.87 | no |
| false positive | SAP (any) | 11070-1641194-1-S | 0.87 | no |
| false positive | SAP (any) | 11070-1634264-1-S | 0.87 | no |
| false positive | Accounting / Buchhaltung | 10001-1003780997-S | 0.73 | yes |
| false positive | Controlling / Reporting | 11070-1531149-2-S | 0.69 | yes |
| false positive | Accounting / Buchhaltung | 13884-141140-S | 0.68 | yes |
| false positive | JavaScript | 16947-930349336-S | 0.68 | yes |
| false positive | SQL | 16947-930349336-S | 0.67 | no |
| false positive | Accounting / Buchhaltung | 10001-1003783349-S | 0.66 | yes |
| false positive | Controlling / Reporting | 10001-1003167615-S | 0.65 | yes |
| false positive | Controlling / Reporting | 11070-1640289-1-S | 0.65 | yes |
| false positive | MS Office | 10001-1003167615-S | 0.65 | yes |
| false positive | MS Office | 10001-1003733612-S | 0.65 | yes |
| false positive | Git | 12811-2332148-S | 0.64 | yes |
| false positive | Accounting / Buchhaltung | 15939-BB-635437-7878-3068-S | 0.64 | yes |
| false positive | Controlling / Reporting | 10001-1003780997-S | 0.64 | yes |
| false positive | MS Office | 13635-eef44b00_JB5249897-S | 0.64 | yes |
| false positive | Controlling / Reporting | 12811-2316142-S | 0.63 | yes |
| false positive | Accounting / Buchhaltung | 16194-00003106c0b001-S | 0.63 | yes |
| false positive | Controlling / Reporting | 10000-1204208432-S | 0.63 | yes |
| missed | Driving licence (B) | 12811-2332148-S | 0.33 | yes |
| missed | Power BI | 11070-1640289-1-S | 0.40 | yes |
| missed | JavaScript | 11070-1634264-1-S | 0.41 | yes |
| missed | Python | 10001-1003484964-S | 0.42 | yes |
| missed | Driving licence (B) | 12951-609453c5-fbb9-4331--S | 0.43 | yes |
| … 31 more | | | | |

## Result

Micro F1 on all 100 postings: Rules 95%, Embeddings 75%, Rules ∪ emb. 91%, Rules ∩ emb. 78%. Best: **Rules**.
