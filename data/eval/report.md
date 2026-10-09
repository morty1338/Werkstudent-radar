# Extraction accuracy

Rules: extractor version 3.

Labelled postings: **100** (random sample: 70). Labelling was blind: the labeller saw the posting text, not the predictions (how the labels were made: [LABELS.md](LABELS.md)). Predictions come from re-running the rules on the same texts.

## Werkstudent filter and job field (random sample)

| Check | Result |
|---|---|
| Posting really is a Werkstudent job | 70/70 (100%) |
| Job field assigned correctly | 55/70 (79%) |

## German requirement

| Check | Result |
|---|---|
| Exact level (required / plus / none / not mentioned), random sample | 69/70 (99%) |
| Open to non-German speakers yes/no, random sample | 70/70 (100%) |
| Postings shown as “open without German” that really are (all strata) | 15/15 (100%) |

Confusion matrix, random sample (rows: label, columns: rules):

| label \ rules | required | plus | none | implicit |
|---|---|---|---|---|
| required | 30 | 0 | 0 | 1 |
| plus | 0 | 1 | 0 | 0 |
| none | 0 | 0 | 0 | 0 |
| implicit | 0 | 0 | 0 | 38 |

## Hourly pay

Pay fields from the API aren't part of this check (the texts are re-analysed alone), so this measures the text rules.

| Check | Result |
|---|---|
| Precision: rules find a rate and the posting states one, random sample | 100% (7/7) |
| Recall: posting states a rate and the rules find it, random sample | 100% (7/7) |
| Amount correct when both found it (all strata) | 19/19 (100%) |
| Rates found in the text that are correct (all strata) | 19/19 (100%) |

## Skills (14 common skills, random sample)

| Skill | In postings | Precision | Recall | F1 |
|---|---|---|---|---|
| MS Office | 28 | 97% | 100% | 98% |
| Excel | 8 | 100% | 100% | 100% |
| PowerPoint | 5 | 100% | 100% | 100% |
| SAP (any) | 7 | 100% | 100% | 100% |
| SQL | 2 | 100% | 100% | 100% |
| Python | 5 | 100% | 100% | 100% |
| Java | 0 | – | – | – |
| JavaScript | 0 | – | – | – |
| Power BI | 1 | 100% | 100% | 100% |
| Git | 1 | 100% | 100% | 100% |
| Controlling / Reporting | 4 | 100% | 75% | 86% |
| Accounting / Buchhaltung | 2 | 100% | 50% | 67% |
| Social media | 1 | 100% | 100% | 100% |
| Driving licence (B) | 5 | 100% | 100% | 100% |
| **All 14** | 69 | **99%** | **97%** | **98%** |

## Disagreements

| Posting | Field | Label | Rules |
|---|---|---|---|
| 10001-1003352753-S | German | required | implicit |
