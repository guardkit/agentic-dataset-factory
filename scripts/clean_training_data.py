#!/usr/bin/env python3
"""Clean defective entries from Long Run 1 training data.

Processes output/train.jsonl and produces output/train_cleaned.jsonl with:
1. Degenerate placeholder entries removed (content == "...")
2. Empty assistant responses removed (think-block only, no visible reply)
3. Unclosed <think> blocks repaired

Usage:
    python -m scripts.clean_training_data [--input PATH] [--output PATH] [--dry-run]
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

_THINK_BLOCK_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)
_UNCLOSED_THINK_RE = re.compile(r"<think>.*", re.DOTALL | re.IGNORECASE)


@dataclass
class CleaningStats:
    """Tracks cleaning operations and outcomes."""

    total: int = 0
    removed_degenerate: int = 0
    removed_empty: int = 0
    repaired_think: int = 0
    unchanged: int = 0
    log_entries: list[dict] = field(default_factory=list)

    @property
    def kept(self) -> int:
        return self.total - self.removed_degenerate - self.removed_empty


def is_degenerate(entry: dict) -> bool:
    """Check if any message has placeholder '...' content."""
    for msg in entry.get("messages", []):
        if msg.get("content", "").strip() == "...":
            return True
    return False


def is_empty_assistant(entry: dict) -> bool:
    """Check if assistant content is empty after stripping think blocks."""
    for msg in entry.get("messages", []):
        if msg.get("role") != "assistant":
            continue
        content = msg.get("content", "")
        stripped = _THINK_BLOCK_RE.sub("", content)
        stripped = _UNCLOSED_THINK_RE.sub("", stripped)
        if not stripped.strip():
            return True
    return False


def has_unclosed_think(entry: dict) -> bool:
    """Check if any assistant message has unclosed <think> blocks."""
    for msg in entry.get("messages", []):
        if msg.get("role") != "assistant":
            continue
        content = msg.get("content", "")
        opens = len(re.findall(r"<think>", content, re.IGNORECASE))
        closes = len(re.findall(r"</think>", content, re.IGNORECASE))
        if opens > closes:
            return True
    return False


def repair_think_blocks(entry: dict) -> dict:
    """Close unclosed <think> blocks in assistant messages.

    Uses the same logic as ``normalise_think_closing_tags()`` from
    synthesis/validator.py.
    """
    entry = json.loads(json.dumps(entry))  # deep copy
    for msg in entry.get("messages", []):
        if msg.get("role") != "assistant":
            continue
        content = msg.get("content", "")
        opens = len(re.findall(r"<think>", content, re.IGNORECASE))
        closes = len(re.findall(r"</think>", content, re.IGNORECASE))
        if opens > closes:
            content = content + "</think>"
            msg["content"] = content
    return entry


def clean_training_data(
    input_path: Path,
    output_path: Path,
    *,
    dry_run: bool = False,
) -> CleaningStats:
    """Process training data, removing/repairing defective entries.

    Args:
        input_path: Path to source train.jsonl
        output_path: Path for cleaned output
        dry_run: If True, analyse only without writing output

    Returns:
        CleaningStats with counts and log entries
    """
    stats = CleaningStats()
    cleaned_entries: list[str] = []

    with open(input_path) as f:
        lines = f.readlines()

    stats.total = len(lines)

    for line_num, raw_line in enumerate(lines, 1):
        raw_line = raw_line.rstrip("\n")
        if not raw_line.strip():
            continue

        entry = json.loads(raw_line)

        # Check 1: Degenerate placeholder
        if is_degenerate(entry):
            stats.removed_degenerate += 1
            stats.log_entries.append(
                {
                    "line": line_num,
                    "defect": "degenerate_placeholder",
                    "action": "removed",
                }
            )
            logger.info("Line %d: removed (degenerate placeholder)", line_num)
            continue

        # Check 2: Empty assistant response
        if is_empty_assistant(entry):
            stats.removed_empty += 1
            stats.log_entries.append(
                {
                    "line": line_num,
                    "defect": "empty_assistant_response",
                    "action": "removed",
                }
            )
            logger.info("Line %d: removed (empty assistant response)", line_num)
            continue

        # Check 3: Unclosed think blocks (repair, don't remove)
        if has_unclosed_think(entry):
            entry = repair_think_blocks(entry)
            stats.repaired_think += 1
            stats.log_entries.append(
                {
                    "line": line_num,
                    "defect": "unclosed_think_block",
                    "action": "repaired",
                }
            )
            logger.info("Line %d: repaired (unclosed think block)", line_num)

        else:
            stats.unchanged += 1

        cleaned_entries.append(json.dumps(entry, ensure_ascii=False))

    if not dry_run:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            f.write("\n".join(cleaned_entries) + "\n" if cleaned_entries else "")

    return stats


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Clean defective entries from training data"
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("output/train.jsonl"),
        help="Input training data file",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("output/train_cleaned.jsonl"),
        help="Output cleaned training data file",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Analyse without writing output",
    )
    parser.add_argument(
        "--log-file",
        type=Path,
        default=None,
        help="Write cleaning log to JSON file",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s: %(message)s",
    )

    if not args.input.exists():
        logger.error("Input file not found: %s", args.input)
        return 1

    stats = clean_training_data(args.input, args.output, dry_run=args.dry_run)

    # Summary
    print(f"\n{'=' * 50}")
    print("Training Data Cleaning Report")
    print(f"{'=' * 50}")
    print(f"Total entries:           {stats.total}")
    print(f"Removed (degenerate):    {stats.removed_degenerate}")
    print(f"Removed (empty assist.): {stats.removed_empty}")
    print(f"Repaired (think tags):   {stats.repaired_think}")
    print(f"Unchanged:               {stats.unchanged}")
    print(f"Entries in output:       {stats.kept}")
    print(f"{'=' * 50}")

    if args.dry_run:
        print("\n[DRY RUN] No output file written.")
    else:
        print(f"\nCleaned data written to: {args.output}")

    # Write log file if requested
    if args.log_file:
        args.log_file.parent.mkdir(parents=True, exist_ok=True)
        log_data = {
            "summary": {
                "total": stats.total,
                "removed_degenerate": stats.removed_degenerate,
                "removed_empty": stats.removed_empty,
                "repaired_think": stats.repaired_think,
                "unchanged": stats.unchanged,
                "kept": stats.kept,
            },
            "entries": stats.log_entries,
        }
        with open(args.log_file, "w") as f:
            json.dump(log_data, f, indent=2)
        print(f"Cleaning log written to: {args.log_file}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
