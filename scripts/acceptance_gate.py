"""Promotion gate for the Rehab Robotics multi-device fleet workflow.

Reads docs/hardware-acceptance-report.md, checks every STATUS marker, and
exits 0 only when all sections are STATUS: PASS.

Usage:
    python scripts/acceptance_gate.py

Exit codes:
    0  — Gate CLOSED: all sections PASS. Safe to set use_fleet_bridge default to true.
    1  — Gate OPEN: one or more sections are PENDING or FAIL.
    2  — Gate ERROR: no STATUS markers found in report (file missing or malformed).
"""
import re
import sys
from pathlib import Path

_REPORT_PATH = Path(__file__).parent.parent / "docs" / "hardware-acceptance-report.md"


def main() -> int:
    """Run the acceptance gate. Returns the exit code."""
    if not _REPORT_PATH.exists():
        print(f"Gate ERROR: report not found at {_REPORT_PATH}", file=sys.stderr)
        return 2

    text = _REPORT_PATH.read_text(encoding="utf-8")

    # Extract section headings: "## 1. Fleet Configuration Tested" etc.
    headings = re.findall(r"(?m)^##\s+\d+\.\s+(.+?)\s*$", text)

    # Extract only line-anchored STATUS markers (avoids matching inline references)
    statuses = re.findall(r"(?m)^STATUS:\s*(\w+)", text)

    if not statuses:
        print("Gate ERROR: no STATUS markers found in report", file=sys.stderr)
        return 2

    open_sections = []
    for i, status in enumerate(statuses):
        if status.upper() != "PASS":
            heading = headings[i] if i < len(headings) else f"Section {i + 1}"
            open_sections.append((i + 1, heading, status))

    if open_sections:
        for section_num, heading, status in open_sections:
            print(f"  [{status}] Section {section_num}: {heading}")
        print(f"\nGate OPEN — {len(open_sections)} section(s) not PASS")
        return 1

    print(f"Gate CLOSED — all {len(statuses)} sections PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
