# How the labels were made

`labels.csv` holds one row per posting in `sample_ids.csv` (reference number and
answers only, no job text).

- **Labeller:** an AI assistant (Claude), not a human. The rules being tested
  were written in the same project, so this is a consistency check against a
  careful second reading, not an independent human evaluation.
- **Pass 1, blind:** every posting text was read in full and labelled before
  any prediction was looked at, following the definitions in
  [`eval/label.html`](../../eval/label.html). A skill counts when the posting
  asks for it (required or nice to have) or names it as a tool the student will
  use; not when it only describes the employer's products.
- **Pass 2, verification:** every disagreement with the rules was re-read
  against the text, plus 15 random agreements. 2 labels changed (both
  "Controlling / Reporting" for reporting-heavy roles); 2 German labels are
  marked ambiguous in the `note` column and kept.
- **Pass 3, rule fixes:** the rules were then improved using these
  disagreements. Scores measured after that on the same sample are optimistic
  (the rules have seen these postings); the first verified scores are the
  honest baseline. Both are reported.

A human can replace or extend these labels with `python -m radar.evaluate label`.
