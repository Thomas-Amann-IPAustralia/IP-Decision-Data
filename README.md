# Open Australian Legal Corpus — IP Filter

Streams the [Open Australian Legal Corpus](https://huggingface.co/datasets/isaacus/open-australian-legal-corpus) (~1.4 billion tokens, 230 k+ documents) and extracts all matters relating to Australian intellectual property law.

## What gets captured

Documents are matched on three signals, applied in order of cost:

| Signal | Examples |
|--------|---------|
| **Act name in metadata** (citation/title/URL) | *Trade Marks Act 1995*, *Patents Act 1990* |
| **Act name in document body** | Any judgment or instrument referencing the above acts |
| **IP concept keyword** (first 4 000 chars) | *patent infringement*, *likelihood of confusion*, *inventive step*, *moral rights* … |

See [`scripts/filter_ip.py`](scripts/filter_ip.py) for the full keyword lists.

## Repository layout

```
.
├── .github/
│   └── workflows/
│       └── ip_filter.yml       # GitHub Actions workflow (free, unlimited for public repos)
├── scripts/
│   ├── filter_ip.py            # Stream → filter → write ip_docs.jsonl
│   └── summarise_ip.py         # Build ip_index.jsonl + ip_summary.md
├── output/                     # Auto-generated; most files committed by CI
│   ├── ip_index.jsonl          # Lightweight index (no text payload)
│   ├── ip_summary.md           # Human-readable report
│   ├── filter_stats.json       # Machine-readable run stats
│   └── filter_run.log          # Full run log
├── requirements.txt
└── .gitignore                  # ip_docs.jsonl excluded (retrieve from Actions artifact)
```

## Running locally

```bash
pip install -r requirements.txt

# Full run
python scripts/filter_ip.py

# Resume an interrupted run
python scripts/filter_ip.py --resume

# Dry run — count matches, write nothing
python scripts/filter_ip.py --dry-run

# Build the summary/index after filtering
python scripts/summarise_ip.py
```

## Running via GitHub Actions

1. **Fork or create** a public repository (free, unlimited Actions minutes).
2. Push this code to `main`.
3. Go to **Actions → IP Corpus Filter → Run workflow**.

The workflow will:
- Stream and filter the corpus (typically 30–90 min)
- Upload `ip_docs.jsonl` as a downloadable workflow artifact (retained 90 days)
- Commit `ip_index.jsonl`, `ip_summary.md`, `filter_stats.json`, and the log back to the repo

A scheduled run fires every Sunday at 02:00 UTC to pick up new corpus releases.

### Retrieving ip_docs.jsonl

The full-text JSONL is excluded from git (it may be several GB). Download it from:

**Actions → (latest run) → Artifacts → ip-docs-\<run number\>**

## Next steps — spaCy NLP

Once you have `ip_docs.jsonl`, pipe it through spaCy:

```python
import json, spacy
from pathlib import Path

nlp = spacy.load("en_core_web_lg")

for line in Path("output/ip_docs.jsonl").open():
    doc_meta = json.loads(line)
    spacy_doc = nlp(doc_meta["text"])
    # your pipeline here …
```

The filtered corpus is small enough to process on a free runner or a laptop.

## Licence

Scripts are MIT-licensed. The corpus itself is licensed under the
[Open Australian Legal Corpus Licence](https://huggingface.co/datasets/isaacus/open-australian-legal-corpus).
