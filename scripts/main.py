#!/usr/bin/env python3
"""
main.py — Master orchestrator for Project R.E.M.

Runs all three sub-pipelines in order for the selected participants:
  1. extraction/pipeline.py  — raw wearable data → per-minute CSVs + activity states
  2. baseline/pipeline.py    — circadian baselines + recovery curves
  3. sessions/pipeline.py    — session effects, arc analysis, significance tests

All three stages always run. Failures are collected and reported at the end.
Skip logic is delegated to each sub-pipeline (freshness checks built in).

Usage:
    uv run python scripts/main.py --all
    uv run python scripts/main.py --participants bosbes peer
    uv run python scripts/main.py --all --skip-extraction
    uv run python scripts/main.py --all --force
"""

import argparse
import subprocess
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent

PARTICIPANTS = [
    "bosbes", "citroen", "kiwi", "kokosnoot",
    "limoen", "peer", "watermeloen", "aardbei",
]

_PIPELINES = [
    ("extraction", SCRIPTS_DIR / "extraction" / "pipeline.py", False),
    ("baseline",   SCRIPTS_DIR / "baseline"   / "pipeline.py", False),
    ("sessions",   SCRIPTS_DIR / "sessions"   / "pipeline.py", True),
    #                                                           ^ uses --participants flag
]


def _run_sub(label: str, script: Path, participants: list[str], force: bool,
             use_named_flag: bool) -> tuple[int, str]:
    """
    Invoke a sub-pipeline, stream its output line-by-line, and return
    (exit_code, tail_of_output_on_failure).

    Participants are passed as positional args (extraction/baseline) or via
    --participants flag (sessions — which uses a mutually exclusive arg group).

    -u makes the sub-pipeline run unbuffered so lines appear immediately even
    when its stdout is a pipe rather than a TTY. stdout and stderr are merged
    (stderr=STDOUT) so error messages stay in sequence with normal output.
    bufsize=1 enables line-buffering on the pipe read side.
    """
    cmd = ["uv", "run", "python", "-u", str(script)]
    if use_named_flag:
        cmd += ["--participants"] + participants
    else:
        cmd += participants
    if force:
        cmd.append("--force")

    print(f"\n  $ {' '.join(str(c) for c in cmd)}\n", flush=True)

    proc = subprocess.Popen(
        cmd,
        cwd=str(SCRIPTS_DIR.parent),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )

    captured: list[str] = []
    for line in proc.stdout:
        print(line, end="", flush=True)
        captured.append(line)

    proc.wait()

    tail = "".join(captured[-10:]) if proc.returncode != 0 else ""
    return proc.returncode, tail.strip()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="R.E.M. master pipeline — extraction → baseline → sessions",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="All three stages always run. Failures are reported at the end.",
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--all", action="store_true",
        help=f"Run all known participants: {', '.join(PARTICIPANTS)}",
    )
    group.add_argument(
        "--participants", nargs="+", metavar="CODENAME",
        help="One or more participant codenames",
    )
    parser.add_argument("--skip-extraction", action="store_true",
                        help="Skip Pipeline 1 (extraction)")
    parser.add_argument("--skip-baseline",   action="store_true",
                        help="Skip Pipeline 2 (baseline)")
    parser.add_argument("--skip-sessions",   action="store_true",
                        help="Skip Pipeline 3 (sessions)")
    parser.add_argument("--force", action="store_true",
                        help="Pass --force to all sub-pipelines (ignore freshness checks)")
    args = parser.parse_args()

    participants = PARTICIPANTS if args.all else args.participants

    skip = {
        "extraction": args.skip_extraction,
        "baseline":   args.skip_baseline,
        "sessions":   args.skip_sessions,
    }

    active = [label for label, _, _ in _PIPELINES if not skip[label]]
    skipped = [label for label in skip if skip[label]]

    print("=" * 60)
    print("  R.E.M. Master Pipeline")
    print("=" * 60)
    print(f"  Participants : {', '.join(participants)}")
    print(f"  Stages       : {', '.join(active) or '(none)'}")
    if skipped:
        print(f"  Skipped      : {', '.join(skipped)}")
    if args.force:
        print("  Mode         : --force (freshness checks bypassed)")
    print(flush=True)

    results: list[tuple[str, int, str]] = []  # (label, exit_code, error_summary)

    for label, script, use_named_flag in _PIPELINES:
        if skip[label]:
            continue

        print("=" * 60)
        print(f"  PIPELINE — {label.upper()}")
        print("=" * 60, flush=True)

        rc, stderr = _run_sub(label, script, participants, args.force, use_named_flag)
        results.append((label, rc, stderr))

        if rc == 0:
            print(f"\n  ✓ {label} complete.", flush=True)
        else:
            print(f"\n  ✗ {label} exited with code {rc}.", flush=True)

    # ── Final report ──────────────────────────────────────────────────────────
    print()
    print("=" * 60)
    print("  FINAL REPORT")
    print("=" * 60)

    failures = [(label, rc, err) for label, rc, err in results if rc != 0]
    successes = [(label, rc, err) for label, rc, err in results if rc == 0]

    for label, _, _ in successes:
        print(f"  ✓  {label:<15}")

    for label, rc, err in failures:
        print(f"  ✗  {label:<15} exit code {rc}")
        if err:
            # Show last 3 lines of stderr as a concise reason
            lines = [ln for ln in err.splitlines() if ln.strip()][-3:]
            for line in lines:
                print(f"       {line}")

    print()
    if failures:
        failed_labels = ", ".join(label for label, _, _ in failures)
        print(f"  {len(failures)} stage(s) failed: {failed_labels}")
        sys.exit(1)
    else:
        print("  All stages completed successfully.")


if __name__ == "__main__":
    main()
