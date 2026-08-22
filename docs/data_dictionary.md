# Data Dictionary — Australian IP Law Corpus

This document describes every field in every data file produced by this repository's pipeline. It covers the full filtered corpus (`ip_docs.jsonl`), the lightweight index committed to git (`ip_index.jsonl`), and the supporting run-metadata files.

*Last reviewed: 2026-08-22, against the run recorded in `output/filter_stats.json` (`run_at: 2026-08-16T03:46:21Z`, 8,900 matched documents).*

## 1. Dataset overview

This repository streams the [Open Australian Legal Corpus](https://huggingface.co/datasets/isaacus/open-australian-legal-corpus) (232,560 documents, ~1.47B tokens) and filters it down to documents relating to Australian intellectual property law — trade marks, patents, copyright, designs, plant breeder's rights, circuit layouts, and related case law and treaties. See `scripts/filter_ip.py` for the full matching logic and README.md for the project overview.

**Pipeline / lineage:**

```
isaacus/open-australian-legal-corpus  (HuggingFace, streamed)
        │
        ▼  scripts/filter_ip.py   (keyword + act-name matching)
        │
        ├──▶ output/ip_docs.jsonl        (full matched documents; git-ignored)
        ├──▶ output/filter_stats.json    (run statistics)
        └──▶ output/filter_run.log       (run log)
                │
                ▼  scripts/summarise_ip.py
                │
                ├──▶ output/ip_index.jsonl   (lightweight index, no text)
                └──▶ output/ip_summary.md    (human-readable report)
```

A GitHub Actions workflow (`.github/workflows/ip_filter.yml`) runs this pipeline on manual dispatch and every Sunday at 02:00 UTC, committing the lightweight outputs back to the repo. `ip_docs.jsonl` itself is never committed — it's uploaded as a 90-day workflow artifact instead (see `.gitignore`).

## 2. Files at a glance

| File | Format | In git? | Row = | Description |
|---|---|---|---|---|
| `output/ip_docs.jsonl` | JSON Lines | **No** (git-ignored; download from Actions artifact) | one matched document, full text | The dataset proper — every field from the source corpus plus a match-reason tag |
| `output/ip_index.jsonl` | JSON Lines | Yes | one matched document, no text | Lightweight pointer/index into the full dataset |
| `output/filter_stats.json` | JSON (single object) | Yes | — | Machine-readable statistics for the most recent filter run |
| `output/ip_summary.md` | Markdown | Yes | — | Human-readable report generated from `ip_index.jsonl` |
| `output/filter_run.log` | Plain text log | Yes | one log line per event | Full log of the most recent filter run |

## 3. `output/ip_docs.jsonl` — full matched documents

Each line is a JSON object. It is the source corpus's document record, passed through unmodified (`**doc`), with one field added by this repository's filter step. Field names, types, and value ranges below for the inherited fields are as documented on the [source dataset card](https://huggingface.co/datasets/isaacus/open-australian-legal-corpus); consult it directly for authoritative, up-to-date ranges, since this repo does not control that schema.

| Field | Type | Nullable | Description |
|---|---|---|---|
| `version_id` | string | No | Unique identifier for the document's latest version, as assigned by the source corpus. |
| `type` | string (enum) | No | Document category. One of: `primary_legislation`, `secondary_legislation`, `bill`, `decision`. |
| `jurisdiction` | string (enum) | No | Issuing jurisdiction. One of: `commonwealth`, `new_south_wales`, `queensland`, `western_australia`, `south_australia`, `tasmania`, `norfolk_island`. (The source corpus itself only covers these 7 jurisdictions — Victoria, ACT, and the Northern Territory are not represented, so IP decisions from those jurisdictions cannot appear here regardless of the filter.) |
| `source` | string (enum) | No | Origin database/registry the document was scraped from, e.g. `federal_register_of_legislation`, `nsw_caselaw`, `high_court_of_australia`. The source corpus documents 8 possible values; this repo does not enumerate the full set. |
| `citation` | string | No | Document title/citation, generally including an abbreviated jurisdiction in parentheses, e.g. `Copyright Act 1968 (Cth)`. |
| `mime` | string (enum) | No | Original content type of the scraped document. One of: `text/html`, `application/pdf`, `application/rtf`, `application/vnd.openxmlformats`. |
| `date` | string (ISO 8601) | **Yes** | Publication/decision date, `YYYY-MM-DDTHH:MM:SS`. Null when the source registry did not supply a date. |
| `url` | string | No | Link to the current version of the document on the source registry's website. |
| `when_scraped` | string (ISO 8601 with timezone) | No | Timestamp the source corpus recorded this document at. |
| `text` | string | No | Full plain-text body of the document. Length ranges from tens of characters (short instruments) to several million (long consolidated Acts). |
| `_ip_match_reason` | string (enum) | No | **Added by this repo** (not part of the source corpus). Explains which signal caused the document to be classified as IP-related. One of `metadata_act`, `body_act`, `body_concept` — see [§6](#6-match-reason--how-a-document-qualifies-as-ip-related). |

Example record (fields abbreviated):

```json
{
  "version_id": "...",
  "type": "decision",
  "jurisdiction": "commonwealth",
  "source": "federal_court_of_australia",
  "citation": "Kosciuszko Thredbo Pty Limited v ThredboNet Marketing Pty Limited [2014] FCAFC 87",
  "mime": "text/html",
  "date": "2014-07-04T00:00:00",
  "url": "https://www.judgments.fedcourt.gov.au/judgments/Judgments/fca/full/2014/2014fcafc0087",
  "when_scraped": "2025-01-01T00:00:00+00:00",
  "text": "IN THE FEDERAL COURT OF AUSTRALIA ...",
  "_ip_match_reason": "body_act"
}
```

**How to get this file:** it is git-ignored (potentially several GB). Download it from **Actions → (latest run) → Artifacts → `ip-docs-<run number>`** (retained 90 days).

## 4. `output/ip_index.jsonl` — lightweight index

Committed to git. Generated by `scripts/summarise_ip.py` as a projection of `ip_docs.jsonl` with `text` and all other bulky/less-used fields dropped, so the full match list can be browsed without cloning a multi-gigabyte file. Currently 8,900 lines (one per matched document).

| Field | Type | Nullable | Description |
|---|---|---|---|
| `citation` | string | No (may be empty string) | Same as `ip_docs.jsonl.citation`. |
| `url` | string | No (may be empty string) | Same as `ip_docs.jsonl.url`. |
| `jurisdiction` | string (enum) | No | Same as `ip_docs.jsonl.jurisdiction`; defaults to `"unknown"` if the source record had no value. |
| `type` | string (enum) | No | Same as `ip_docs.jsonl.type`; defaults to `"unknown"` if the source record had no value. |
| `match_reason` | string (enum) | No (may be empty string) | Same as `ip_docs.jsonl._ip_match_reason`. |

**Not carried over from `ip_docs.jsonl`:** `version_id`, `source`, `mime`, `date`, `when_scraped`, `text`. There is no synthetic row ID or `version_id` in this file — `citation` + `url` together are the closest thing to a natural key for joining back to a downloaded `ip_docs.jsonl`, though neither is formally guaranteed unique by the pipeline.

## 5. `output/filter_stats.json` — run statistics

A single JSON object, overwritten each run.

| Field | Type | Description |
|---|---|---|
| `run_at` | string (ISO 8601 UTC) | Timestamp the filter run completed. |
| `total_streamed` | integer | Total documents pulled from the source corpus stream. |
| `total_fast_forwarded` | integer | Documents skipped because `--resume` fast-forwarded past a prior partial run. |
| `total_evaluated` | integer | `total_streamed − total_fast_forwarded`; documents actually run through the matcher. |
| `total_matched` | integer | Documents classified as IP-related (same count as lines in `ip_docs.jsonl` / `ip_index.jsonl`). |
| `match_rate_pct` | float | `total_matched / total_evaluated × 100`, rounded to 4 decimal places. |
| `match_reasons` | object `{string: integer}` | Count of matched documents per `_ip_match_reason` value: keys `metadata_act`, `body_act`, `body_concept`. |
| `elapsed_seconds` | float | Wall-clock run time. |
| `output_file` | string | Relative path the full corpus was written to (`output/ip_docs.jsonl`). |
| `ip_acts_in_scope` | array of strings | The exact `IP_ACTS` list from `scripts/filter_ip.py` at run time — act/instrument/body names matched against citation, title, URL, and full text. |
| `ip_concepts_in_scope` | array of strings | The exact `IP_CONCEPTS` list from `scripts/filter_ip.py` at run time — keyword phrases matched against only the first 4,000 characters of document text. |

## 6. `match_reason` / `_ip_match_reason` — how a document qualifies as IP-related

Documents are tested against three signals, in this order, evaluated by `is_ip_document()` in `scripts/filter_ip.py`. The first signal that hits wins (a document is not double-counted):

| Value | Meaning | Signal tested | Latest run count |
|---|---|---|---|
| `metadata_act` | Name of an in-scope Act/instrument/body appears in the document's citation, title, or URL. | `IP_ACTS` list against `citation + title + url` | 226 |
| `body_act` | Name of an in-scope Act/instrument/body appears somewhere in the full document text (but not in the metadata above). | `IP_ACTS` list against the entire `text` field | 4,154 |
| `body_concept` | No named Act matched, but an IP concept keyword (e.g. `patent infringement`, `moral rights`, `prior art`) appears in the opening of the document. | `IP_CONCEPTS` list against the first 4,000 characters of `text` only | 4,520 |

Because `body_concept` only scans the first 4,000 characters, a long document whose only IP-relevant language appears later in the body will not match on that signal (it may still match on `body_act`, which scans the full text).

## 7. Enumerated values reference (latest run: 8,900 documents)

**`jurisdiction`** (7 values):

| Value | Documents |
|---|---|
| `commonwealth` | 6,250 |
| `new_south_wales` | 2,135 |
| `queensland` | 181 |
| `western_australia` | 139 |
| `norfolk_island` | 93 |
| `south_australia` | 75 |
| `tasmania` | 27 |

**`type`** (4 values):

| Value | Documents |
|---|---|
| `decision` | 7,282 |
| `secondary_legislation` | 929 |
| `primary_legislation` | 553 |
| `bill` | 136 |

**`mime`** (inherited from source corpus; not broken out per-run in this repo's stats): `text/html`, `application/pdf`, `application/rtf`, `application/vnd.openxmlformats`.

Full breakdowns (including per-Act reference counts) are regenerated on every run in `output/ip_summary.md`.

## 8. `output/ip_summary.md` and `output/filter_run.log`

These are not structured/tabular data but are listed here for completeness:

- **`ip_summary.md`** — Markdown report generated by `scripts/summarise_ip.py`: overview counts, breakdowns by jurisdiction/type/match signal, approximate per-Act reference counts (Act names scanned across `citation + text[:8000]`), and up to 5 sample documents per jurisdiction.
- **`filter_run.log`** — plain-text log from `scripts/filter_ip.py`, one line per event, format: `YYYY-MM-DDTHH:MM:SS  LEVEL     message`. Includes a progress line every 5,000 documents streamed and a final summary block matching `filter_stats.json`.

## 9. Licensing

- **Corpus content** (`ip_docs.jsonl`, `ip_index.jsonl`, and any text derived from them): the compiled Open Australian Legal Corpus is licensed under CC BY 4.0; individual documents retain their original source licenses (Australian government legal material is generally free to reuse). See the [source dataset licence](https://huggingface.co/datasets/isaacus/open-australian-legal-corpus).
- **Scripts and this documentation**: MIT (see `LICENSE`).

## 10. Known limitations

- **`ip_docs.jsonl` is not in this repository.** It's git-ignored because it can run into the gigabytes; retrieve it from the corresponding GitHub Actions run's artifacts (90-day retention). Everything else in `output/` is derived from it.
- **`ip_index.jsonl` has no stable primary key.** Use `citation` + `url` to cross-reference a downloaded `ip_docs.jsonl`; neither field is enforced unique by the pipeline.
- **Keyword matching is a heuristic, not legal curation.** `IP_ACTS`/`IP_CONCEPTS` matching (see `scripts/filter_ip.py`) can both over-match (e.g. generic uses of "design" or "licence" unrelated to IP law) and under-match (an IP case that never uses any listed keyword in the first 4,000 characters and never names a listed Act). Treat this as a recall-oriented filter, not a verified IP-law dataset.
- **`jurisdiction` coverage is inherited, not a filtering choice.** The upstream Open Australian Legal Corpus itself only covers 7 of Australia's jurisdictions (no Victoria, ACT, or Northern Territory), so IP matters from those jurisdictions cannot appear in this dataset no matter how the filter is tuned.
- **Act-reference counts in `ip_summary.md` are approximate**, since they only scan the first 8,000 characters of `citation + text` per document (see `extract_act_references()` in `scripts/summarise_ip.py`).
- **No deduplication.** If the source corpus contains multiple version records for the same underlying document, each matching version is written as a separate row.
