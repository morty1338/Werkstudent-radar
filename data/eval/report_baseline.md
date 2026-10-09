# Extraction accuracy

Rules: extractor version 2.

Labelled postings: **100** (random sample: 70). Labelling was blind: the labeller saw the posting text, not the predictions (how the labels were made: [LABELS.md](LABELS.md)). Predictions come from re-running the rules on the same texts.

## Werkstudent filter and job field (random sample)

| Check | Result |
|---|---|
| Posting really is a Werkstudent job | 70/70 (100%) |
| Job field assigned correctly | 45/70 (64%) |

## German requirement

| Check | Result |
|---|---|
| Exact level (required / plus / none / not mentioned), random sample | 66/70 (94%) |
| Open to non-German speakers yes/no, random sample | 70/70 (100%) |
| Postings shown as “open without German” that really are (all strata) | 15/22 (68%) |

Confusion matrix, random sample (rows: label, columns: rules):

| label \ rules | required | plus | none | implicit |
|---|---|---|---|---|
| required | 27 | 0 | 0 | 4 |
| plus | 0 | 1 | 0 | 0 |
| none | 0 | 0 | 0 | 0 |
| implicit | 0 | 0 | 0 | 38 |

## Hourly pay

Pay fields from the API aren't part of this check (the texts are re-analysed alone), so this measures the text rules.

| Check | Result |
|---|---|
| Precision: rules find a rate and the posting states one, random sample | 100% (7/7) |
| Recall: posting states a rate and the rules find it, random sample | 100% (7/7) |
| Amount correct when both found it (all strata) | 18/19 (95%) |
| Rates found in the text that are correct (all strata) | 18/19 (95%) |

## Skills (14 common skills, random sample)

| Skill | In postings | Precision | Recall | F1 |
|---|---|---|---|---|
| MS Office | 28 | 97% | 100% | 98% |
| Excel | 8 | 100% | 100% | 100% |
| PowerPoint | 5 | 100% | 100% | 100% |
| SAP (any) | 7 | 100% | 100% | 100% |
| SQL | 2 | 100% | 100% | 100% |
| Python | 5 | 100% | 80% | 89% |
| Java | 0 | – | – | – |
| JavaScript | 0 | – | – | – |
| Power BI | 1 | 100% | 100% | 100% |
| Git | 1 | 100% | 100% | 100% |
| Controlling / Reporting | 4 | 100% | 75% | 86% |
| Accounting / Buchhaltung | 2 | 100% | 50% | 67% |
| Social media | 1 | 100% | 100% | 100% |
| Driving licence (B) | 5 | 100% | 100% | 100% |
| **All 14** | 69 | **99%** | **96%** | **97%** |

## Disagreements

| Posting | Field | Label | Rules |
|---|---|---|---|
| 10000-1204208432-S | German | required | plus |
| 10001-1001115203-S | German | required | none |
| 10001-1003352753-S | German | required | implicit |
| 10001-1003646375-S | pay | 14.50–16.00 | 14.50–14.50 |
| 10001-1003765437-S | German | required | implicit |
| 10001-1003780997-S | German | required | plus |
| 11070-1608471-1-S | German | required | none |
| 11070-1623685-1-S | German | required | none |
| 13151-1634139-1-S | German | required | implicit |
| 13465-00021a67ccf001-S | German | required | plus |
| 16470-44477916-101-S | German | required | implicit |
| 16947-919432708-S | German | required | plus |
| 16947-928317271-S | German | plus | none |
| 16947-963359777-S | German | plus | none |
