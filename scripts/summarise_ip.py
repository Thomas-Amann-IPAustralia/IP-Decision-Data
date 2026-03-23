"""
summarise_ip.py
---------------
Reads output/ip_docs.jsonl (produced by filter_ip.py) and generates:

  output/ip_summary.md   — human-readable markdown report
  output/ip_index.jsonl  — lightweight index (citation, url, jurisdiction,
                           type, match_reason) without the full text payload,
                           suitable for quick lookups and committing to the repo
                           without bloating git history with multi-GB text blobs.

Usage:
    python scripts/summarise_ip.py
"""

import json
import logging
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

# Allow importing filter_ip from the same directory when run as a script
sys.path.insert(0, str(Path(__file__).resolve().parent))
from filter_ip import IP_ACTS

OUTPUT_DIR = Path("output")
INPUT_FILE = OUTPUT_DIR / "ip_docs.jsonl"
SUMMARY_FILE = OUTPUT_DIR / "ip_summary.md"
INDEX_FILE = OUTPUT_DIR / "ip_index.jsonl"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
    stream=sys.stdout,
)
log = logging.getLogger("summarise_ip")


def load_docs(path: Path):
    """Yield parsed records from a JSONL file."""
    with path.open("r", encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, 1):
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError as exc:
                log.warning(f"Line {lineno}: JSON parse error — {exc}")


def extract_act_references(text: str, citation: str) -> list[str]:
    """
    Return a deduplicated list of IP act names found in text or citation.
    Uses the same IP_ACTS list as filter_ip.py for consistency.
    Ordered by first appearance.
    """
    found = []
    combined = f"{citation} {text[:8_000]}"
    for act in IP_ACTS:
        if re.search(re.escape(act), combined, re.IGNORECASE) and act not in found:
            found.append(act)
    return found


def main() -> None:
    if not INPUT_FILE.exists():
        log.error(f"{INPUT_FILE} not found. Run filter_ip.py first.")
        sys.exit(1)

    log.info(f"Reading {INPUT_FILE} …")

    # Accumulators
    total = 0
    jurisdictions: Counter = Counter()
    doc_types: Counter = Counter()
    match_reasons: Counter = Counter()
    act_refs: Counter = Counter()
    # jurisdiction → list of (citation, url)
    sample_by_jurisdiction: defaultdict = defaultdict(list)
    MAX_SAMPLES = 5

    index_records: list[dict] = []

    for doc in load_docs(INPUT_FILE):
        total += 1

        jurisdiction = doc.get("jurisdiction") or "unknown"
        doc_type = doc.get("type") or "unknown"
        citation = doc.get("citation") or ""
        url = doc.get("url") or ""
        reason = doc.get("_ip_match_reason") or ""
        text = doc.get("text") or ""

        jurisdictions[jurisdiction] += 1
        doc_types[doc_type] += 1
        match_reasons[reason] += 1

        for act in extract_act_references(text, citation):
            act_refs[act] += 1

        if len(sample_by_jurisdiction[jurisdiction]) < MAX_SAMPLES:
            sample_by_jurisdiction[jurisdiction].append((citation, url))

        # Write a lightweight index record (no text)
        index_records.append({
            "citation": citation,
            "url": url,
            "jurisdiction": jurisdiction,
            "type": doc_type,
            "match_reason": reason,
        })

    log.info(f"Loaded {total:,} documents. Building report…")

    # -----------------------------------------------------------------------
    # Write index JSONL
    # -----------------------------------------------------------------------
    with INDEX_FILE.open("w", encoding="utf-8") as fh:
        for rec in index_records:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    log.info(f"Index written → {INDEX_FILE}")

    # -----------------------------------------------------------------------
    # Write markdown summary
    # -----------------------------------------------------------------------
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines: list[str] = []

    lines += [
        "# IP Corpus — Filter Summary",
        "",
        f"*Generated: {now}*  ",
        f"*Source: [isaacus/open-australian-legal-corpus](https://huggingface.co/datasets/isaacus/open-australian-legal-corpus)*",
        "",
        "---",
        "",
        "## Overview",
        "",
        f"| Metric | Count |",
        f"|--------|-------|",
        f"| Total IP documents | {total:,} |",
        f"| Jurisdictions | {len(jurisdictions):,} |",
        f"| Document types | {len(doc_types):,} |",
        "",
    ]

    lines += [
        "## By jurisdiction",
        "",
        "| Jurisdiction | Documents |",
        "|---|---|",
    ]
    for jur, count in jurisdictions.most_common():
        lines.append(f"| {jur} | {count:,} |")
    lines.append("")

    lines += [
        "## By document type",
        "",
        "| Type | Documents |",
        "|---|---|",
    ]
    for dt, count in doc_types.most_common():
        lines.append(f"| {dt} | {count:,} |")
    lines.append("")

    lines += [
        "## By match signal",
        "",
        "| Signal | Documents |",
        "|---|---|",
    ]
    signal_labels = {
        "metadata_act": "Act name in citation/title/URL",
        "body_act": "Act name in document body",
        "body_concept": "IP concept keyword in document opening",
    }
    for reason, count in match_reasons.most_common():
        label = signal_labels.get(reason, reason)
        lines.append(f"| {label} | {count:,} |")
    lines.append("")

    lines += [
        "## Act references (approximate)",
        "",
        "Counts documents mentioning each Act at least once.",
        "",
        "| Act | Documents |",
        "|---|---|",
    ]
    for act, count in act_refs.most_common():
        lines.append(f"| {act} | {count:,} |")
    lines.append("")

    lines += ["## Sample documents by jurisdiction", ""]
    for jur in sorted(sample_by_jurisdiction):
        lines.append(f"### {jur.title()}")
        lines.append("")
        for citation, url in sample_by_jurisdiction[jur]:
            display = citation[:100] if citation else "(no citation)"
            if url:
                lines.append(f"- [{display}]({url})")
            else:
                lines.append(f"- {display}")
        lines.append("")

    lines += [
        "---",
        "",
        "## Files",
        "",
        "| File | Description |",
        "|---|---|",
        "| `output/ip_docs.jsonl` | Full document text + metadata (large; git-ignored by default) |",
        "| `output/ip_index.jsonl` | Lightweight index — citation, URL, jurisdiction, type, match reason |",
        "| `output/ip_summary.md` | This file |",
        "| `output/filter_stats.json` | Machine-readable run statistics |",
        "| `output/filter_run.log` | Full filter run log |",
        "",
    ]

    SUMMARY_FILE.write_text("\n".join(lines), encoding="utf-8")
    log.info(f"Summary written → {SUMMARY_FILE}")
    log.info("Done.")


if __name__ == "__main__":
    main()
