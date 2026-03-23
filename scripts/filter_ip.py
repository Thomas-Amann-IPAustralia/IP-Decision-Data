"""
filter_ip.py
------------
Streams the Open Australian Legal Corpus and filters for documents relating to
intellectual property law (Trade Marks, Patents, Copyright, Designs, etc.).

Writes matched documents incrementally to output/ip_docs.jsonl so that partial
results are never lost, even if the job is interrupted.

Usage:
    python scripts/filter_ip.py [--resume] [--dry-run]

Flags:
    --resume    Skip documents already written to ip_docs.jsonl (counts existing
                lines and fast-forwards the stream). Useful if a job timed out.
    --dry-run   Print match counts and sample citations without writing any files.
"""

import argparse
import json
import logging
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

OUTPUT_DIR = Path("output")
OUTPUT_FILE = OUTPUT_DIR / "ip_docs.jsonl"
STATS_FILE = OUTPUT_DIR / "filter_stats.json"
LOG_FILE = OUTPUT_DIR / "filter_run.log"

# Legislation that is explicitly in scope.
# Patterns are matched case-insensitively against citation, title, and text.
IP_ACTS: list[str] = [
    # Commonwealth primary legislation
    "Trade Marks Act",
    "Patents Act",
    "Copyright Act",
    "Designs Act",
    "Plant Breeder's Rights Act",
    "Plant Breeders Rights Act",           # alternate spelling
    "Circuit Layouts Act",
    "Olympic Insignia Protection Act",
    "Geographical Indications",            # covers 2023 Act and related instruments
    "Intellectual Property Laws Amendment",
    "IP Laws Amendment",
    # Subordinate legislation / instruments
    "Trade Marks Regulations",
    "Patents Regulations",
    "Copyright Regulations",
    "Designs Regulations",
    # Key bodies
    "IP Australia",
    "Commissioner of Patents",
    "Registrar of Trade Marks",
    "Registrar of Designs",
    # International instruments incorporated into Australian law
    "Paris Convention",
    "Patent Cooperation Treaty",
    "Madrid Protocol",
    "Berne Convention",
    "TRIPS Agreement",
    "WIPO",
]

# Broader conceptual keywords — these catch case law that never names a specific Act
# but is clearly about IP. Applied only to the first 4 000 characters of text to
# keep the streaming pass fast.
IP_CONCEPTS: list[str] = [
    "intellectual property",
    "trade mark",
    "trademark",
    "patent",
    "copyright",
    "design right",
    "registered design",
    "plant variety",
    "circuit layout",
    "passing off",
    "infringement of patent",
    "patent infringement",
    "patent claim",
    "copyright infringement",
    "trade mark infringement",
    "likelihood of confusion",
    "distinctiveness",
    "prior art",
    "inventive step",
    "novelty",
    "patentee",
    "licensee",
    "licensor",
    "moral rights",
    "fair dealing",
    "compulsory licence",
    "design infringement",
    "breach of confidence",
    "confidential information",
    "counterfeit",
    "trade secret",
    "misappropriation",
    "unauthorised use",
]

# Pre-compile patterns for speed
_ACT_PATTERNS = [re.compile(re.escape(a), re.IGNORECASE) for a in IP_ACTS]
_CONCEPT_PATTERNS = [re.compile(r"\b" + re.escape(c) + r"\b", re.IGNORECASE) for c in IP_CONCEPTS]

# How many characters of the document body to scan for concept keywords.
# Scanning the full text of 230 k documents is slow; the lede almost always
# appears in the first few kilobytes.
CONCEPT_SCAN_CHARS = 4_000

# Log progress every N documents (across the whole stream, not just matches)
LOG_EVERY = 5_000


# ---------------------------------------------------------------------------
# Matching logic
# ---------------------------------------------------------------------------

def _matches_act(text: str) -> bool:
    """Return True if the text contains the name of an IP act or instrument."""
    return any(p.search(text) for p in _ACT_PATTERNS)


def _matches_concept(text: str) -> bool:
    """Return True if the text contains broad IP conceptual language."""
    excerpt = text[:CONCEPT_SCAN_CHARS]
    return any(p.search(excerpt) for p in _CONCEPT_PATTERNS)


def is_ip_document(doc: dict) -> tuple[bool, str]:
    """
    Classify a corpus document as IP-related or not.

    Returns (matched: bool, reason: str) where reason is a short tag
    explaining which signal triggered the match — useful for auditing.
    """
    citation = doc.get("citation") or ""
    title = doc.get("title") or ""
    url = doc.get("url") or ""
    text = doc.get("text") or ""

    # 1. Metadata signals (cheapest — check first)
    meta = f"{citation} {title} {url}"
    if _matches_act(meta):
        return True, "metadata_act"

    # 2. Act names in the document body
    if _matches_act(text):
        return True, "body_act"

    # 3. Conceptual keywords in the document opening
    if _matches_concept(text):
        return True, "body_concept"

    return False, ""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def count_existing_lines(path: Path) -> int:
    """Count non-empty lines in an existing JSONL file (fast line-count)."""
    if not path.exists():
        return 0
    count = 0
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                count += 1
    return count


def setup_logging(dry_run: bool) -> logging.Logger:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("filter_ip")
    logger.setLevel(logging.DEBUG)
    fmt = logging.Formatter("%(asctime)s  %(levelname)-8s  %(message)s",
                            datefmt="%Y-%m-%dT%H:%M:%S")
    # Console handler
    ch = logging.StreamHandler(sys.stdout)
    ch.setFormatter(fmt)
    logger.addHandler(ch)
    # File handler (skip in dry-run)
    if not dry_run:
        fh = logging.FileHandler(LOG_FILE, mode="a", encoding="utf-8")
        fh.setFormatter(fmt)
        logger.addHandler(fh)
    return logger


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Filter IP documents from the Open Australian Legal Corpus.")
    parser.add_argument("--resume", action="store_true",
                        help="Fast-forward past already-written documents.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Count matches only; do not write any files.")
    args = parser.parse_args()

    logger = setup_logging(args.dry_run)
    logger.info("=" * 60)
    logger.info("filter_ip.py — Open Australian Legal Corpus IP filter")
    logger.info(f"Started at {datetime.now(timezone.utc).isoformat()}")
    logger.info(f"dry_run={args.dry_run}  resume={args.resume}")

    # Lazy import so the script fails fast if datasets isn't installed
    try:
        from datasets import load_dataset
    except ImportError:
        logger.error("'datasets' package not found. Run: pip install datasets")
        sys.exit(1)

    # Determine resume offset
    skip_n = 0
    if args.resume and not args.dry_run:
        skip_n = count_existing_lines(OUTPUT_FILE)
        if skip_n:
            logger.info(f"Resuming: skipping first {skip_n:,} stream documents "
                        f"(already written to {OUTPUT_FILE})")

    # Open output file (append if resuming, write if fresh)
    write_mode = "a" if (args.resume and skip_n > 0) else "w"
    out_fh = None
    if not args.dry_run:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        out_fh = OUTPUT_FILE.open(write_mode, encoding="utf-8")

    # -----------------------------------------------------------------------
    # Stream the corpus
    # -----------------------------------------------------------------------
    logger.info("Loading corpus stream (this may take a moment)…")
    corpus = load_dataset(
        "isaacus/open-australian-legal-corpus",
        split="corpus",
        streaming=True,
        trust_remote_code=True,
    )

    total_seen = 0
    total_skipped = 0   # fast-forwarded
    total_matched = 0
    reason_counts: dict[str, int] = {}
    start_time = time.monotonic()

    try:
        for doc in corpus:
            total_seen += 1

            # Fast-forward past already-written documents when resuming
            if total_seen <= skip_n:
                total_skipped += 1
                if total_skipped % 10_000 == 0:
                    logger.info(f"Fast-forwarding… {total_skipped:,}/{skip_n:,}")
                continue

            matched, reason = is_ip_document(doc)

            if matched:
                total_matched += 1
                reason_counts[reason] = reason_counts.get(reason, 0) + 1

                if args.dry_run:
                    # Just log a sample
                    if total_matched <= 20:
                        logger.info(f"  MATCH [{reason}] {doc.get('citation', '(no citation)')[:120]}")
                else:
                    # Write the full document as a JSONL record, adding match metadata
                    record = {**doc, "_ip_match_reason": reason}
                    out_fh.write(json.dumps(record, ensure_ascii=False) + "\n")
                    # Flush periodically so we don't lose data on timeout
                    if total_matched % 100 == 0:
                        out_fh.flush()

            # Progress log
            effective_seen = total_seen - total_skipped
            if effective_seen % LOG_EVERY == 0:
                elapsed = time.monotonic() - start_time
                rate = effective_seen / elapsed if elapsed > 0 else 0
                logger.info(
                    f"Progress: {total_seen:,} streamed | "
                    f"{total_matched:,} matched | "
                    f"{rate:,.0f} docs/sec"
                )

    finally:
        if out_fh:
            out_fh.flush()
            out_fh.close()

    # -----------------------------------------------------------------------
    # Final stats
    # -----------------------------------------------------------------------
    elapsed = time.monotonic() - start_time
    effective_seen = total_seen - total_skipped
    match_rate = (total_matched / effective_seen * 100) if effective_seen else 0

    logger.info("=" * 60)
    logger.info("COMPLETE")
    logger.info(f"  Documents streamed (total):   {total_seen:,}")
    logger.info(f"  Documents fast-forwarded:     {total_skipped:,}")
    logger.info(f"  Documents evaluated:          {effective_seen:,}")
    logger.info(f"  IP documents matched:         {total_matched:,}  ({match_rate:.2f}%)")
    logger.info(f"  Match reasons breakdown:")
    for reason, count in sorted(reason_counts.items(), key=lambda x: -x[1]):
        logger.info(f"    {reason:<25} {count:,}")
    logger.info(f"  Wall time:                    {elapsed / 60:.1f} min")
    if not args.dry_run:
        size_mb = OUTPUT_FILE.stat().st_size / 1_048_576 if OUTPUT_FILE.exists() else 0
        logger.info(f"  Output file:                  {OUTPUT_FILE}  ({size_mb:.1f} MB)")

    # Write machine-readable stats
    if not args.dry_run:
        stats = {
            "run_at": datetime.now(timezone.utc).isoformat(),
            "total_streamed": total_seen,
            "total_fast_forwarded": total_skipped,
            "total_evaluated": effective_seen,
            "total_matched": total_matched,
            "match_rate_pct": round(match_rate, 4),
            "match_reasons": reason_counts,
            "elapsed_seconds": round(elapsed, 1),
            "output_file": str(OUTPUT_FILE),
            "ip_acts_in_scope": IP_ACTS,
            "ip_concepts_in_scope": IP_CONCEPTS,
        }
        STATS_FILE.write_text(json.dumps(stats, indent=2, ensure_ascii=False))
        logger.info(f"  Stats written to:             {STATS_FILE}")

    logger.info("=" * 60)


if __name__ == "__main__":
    main()
