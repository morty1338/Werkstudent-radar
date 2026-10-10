# Experiments

Side studies that don't run in the daily pipeline. They have their own
dependencies (`requirements.txt` here, not the project's), so the daily
workflow and CI stay small and fast.

## Skill extraction with sentence embeddings

[`skill_embeddings.py`](skill_embeddings.py) asks whether a multilingual
sentence-embedding model finds the skills a posting asks for better than the
regex rules in [`radar/extract.py`](../radar/extract.py). Full results:
[`report.md`](report.md).

**Method.** Each posting (title and text) is cut into phrases: bullet points,
sentences, and overlapping 40-word windows for long ones. Each of the 14
labelled skills gets 2–4 hand-written anchor phrases in German and English
("sehr gute Excel-Kenntnisse", "valid driver's license"). A posting asks for a
skill when some phrase has cosine similarity ≥ t to some anchor. Model:
`paraphrase-multilingual-MiniLM-L12-v2` (0.2 GB) via fastembed/ONNX on CPU.
The threshold t is chosen by 5-fold cross-validation over postings, so the
embeddings are scored on postings their threshold wasn't fitted to. Ground
truth: the 100 labelled postings in `data/eval/` (labels by an AI assistant,
see [LABELS.md](../data/eval/LABELS.md)).

**Result (micro over 14 skills).**

| Method | All 100 postings: P / R / F1 | Random 70: P / R / F1 |
|---|---|---|
| Rules | 94% / 96% / **95%** | 99% / 97% / **98%** |
| Embeddings | 80% / 69% / 75% | 87% / 75% / 81% |
| Rules or embeddings | 84% / 99% / 91% | 88% / 100% / 94% |
| Rules and embeddings | 95% / 66% / 78% | 100% / 72% / 84% |

**Why the embeddings lose.** Skills here are mostly named tools. A phrase like
"MS Office (Word, Excel, PowerPoint)" is about Office as a whole, so its
embedding sits near the MS Office anchors and far from "PowerPoint skills":
PowerPoint recall is 12%, Java 0%. Similarity also rewards topic over
requirement: postings *about* accounting or reporting teams score high for
those skills even when they don't ask for them (most false positives). The
rules look for the exact names and miss only unusual wordings.

Where embeddings help: they found two of three social media postings, the rules
one. Of the two the rules missed, one says "social media" but without the
requirement cue the rule needs for this skill (social media is context-required,
so an employer describing its own channels doesn't count), and one names only
LinkedIn. Adding embeddings as a second opinion ("rules or embeddings") raises
recall to 99% but costs more precision than it gains.

**Recommendation: keep the rules; don't replace or combine.** The embeddings
are clearly worse alone and don't improve F1 combined, while costing ~0.7–0.9 s
of CPU per posting and a 0.2 GB model in the daily run. Two cheap takeaways for
the rules instead: (1) look at the social media cue words, checked against the
labelled sample first (a bare "LinkedIn" is risky: "follow us on LinkedIn" is
common); (2) the
three SAP false positives (for rules and embeddings alike) are postings by SAP
itself, where "SAP" is the employer's name, not a skill asked for; skipping the
skill when the employer is SAP would fix them. Labels
cover only 14 skills with few positives each (2–39), so per-skill numbers are
rough; the micro totals are the reliable part. A larger model
(`paraphrase-multilingual-mpnet-base-v2`, 1 GB: `--model`) or per-skill
thresholds would be the next things to try, but per-skill thresholds need more
labelled positives than 100 postings give.

**Run it** (needs `data/eval/sample.json`, the local, unpublished job texts):

```bash
python3 -m venv experiments/.venv
experiments/.venv/bin/pip install -r experiments/requirements.txt
experiments/.venv/bin/python experiments/skill_embeddings.py
```

The model is downloaded once into `experiments/.cache/` (git-ignored). The
report contains scores and reference numbers only, never job text.
