"""Run the golden eval cases against a real model and write a markdown report.

Usage:
    uv run python evals/run_evals.py [--cases name1,name2] [--out evals/reports/latest.md]

Environment:
    OLLAMA_MODEL / PLANNER_LAB_MODEL_PROVIDER select the model (same as the CLI).
    EVAL_MIN_APPROVAL (default 0.0): exit nonzero when the approval rate is lower.

Two failure classes are distinguished deliberately:
- Deterministic invariant breaches (a recorded ledger value differs from the
  golden expectation) are code regressions and always fail the run.
- Critic rejections are the system refusing to emit an unverifiable memo; they
  lower the approval rate but only fail the run below EVAL_MIN_APPROVAL.
"""

import argparse
import datetime
import importlib.metadata
import os
import platform
import sys
import time
from pathlib import Path
from typing import Any

import yaml
from rich.console import Console

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from planner_lab.agents.models import build_model  # noqa: E402
from planner_lab.agents.pipeline import run_analysis  # noqa: E402
from planner_lab.memo.render import MemoRejectedError  # noqa: E402
from planner_lab.schemas.case_file import CaseFile  # noqa: E402

GOLDEN_DIR = Path(__file__).parent / "golden"


def check_ledger(result: Any, checks: list[dict[str, Any]]) -> list[str]:
    breaches = []
    for check in checks:
        matches = [
            e
            for e in result.ledger.entries
            if e.tool_name == check["tool"]
            and (check.get("label") is None or e.assumptions_label == check["label"])
        ]
        if not matches:
            breaches.append(f"{check['tool']} ({check.get('label')}): no ledger entry")
            continue
        if "value" not in check:
            continue
        actual = matches[0].outputs.get(check["key"])
        if actual is None or abs(float(actual) - float(check["value"])) > 1e-6:
            breaches.append(
                f"{check['tool']}#{check['key']}: expected {check['value']}, got {actual}"
            )
    return breaches


def run_case(path: Path) -> dict[str, Any]:
    doc = yaml.safe_load(path.read_text())
    case = CaseFile.model_validate(doc["case"])
    started = time.monotonic()
    record: dict[str, Any] = {"name": doc["name"], "simulate": doc.get("simulate", False)}
    try:
        result = run_analysis(
            case,
            simulate=doc.get("simulate", False),
            confirm=lambda _: True,
            console=Console(quiet=True),
        )
        record["approved"] = True
        record["failed_checks"] = [c.check_id for c in result.report.checks if not c.passed]
        record["breaches"] = check_ledger(result, doc["expect"].get("ledger_checks", []))
    except MemoRejectedError as e:
        record["approved"] = False
        record["failed_checks"] = [c.check_id for c in e.report.blockers()]
        record["breaches"] = []
    except Exception as e:  # infrastructure failure, not a memo judgment
        record["approved"] = False
        record["failed_checks"] = [f"error: {type(e).__name__}: {e}"]
        record["breaches"] = [f"run crashed: {e}"]
    record["seconds"] = round(time.monotonic() - started, 1)
    return record


def write_report(records: list[dict[str, Any]], out: Path) -> None:
    model = os.environ.get("OLLAMA_MODEL", "qwen3")
    provider = os.environ.get("PLANNER_LAB_MODEL_PROVIDER", "ollama")
    approved = sum(1 for r in records if r["approved"])
    lines = [
        "# Eval report",
        "",
        f"- Date: {datetime.date.today().isoformat()}",
        f"- Model: {provider}:{model}",
        f"- planner-lab: {importlib.metadata.version('planner-lab')}",
        f"- Python: {platform.python_version()}",
        f"- Approval rate: {approved}/{len(records)}",
        "",
        "A rejection means the critic refused to emit an unverifiable memo,",
        "which is the designed failure mode; the score measures how often the",
        "model produces a memo that survives every deterministic check.",
        "",
        "| Case | Simulate | Approved | Failed checks | Ledger breaches | Seconds |",
        "|---|---|---|---|---|---|",
    ]
    for r in records:
        lines.append(
            f"| {r['name']} | {'yes' if r['simulate'] else 'no'} | "
            f"{'yes' if r['approved'] else 'NO'} | "
            f"{', '.join(str(c) for c in r['failed_checks']) or '-'} | "
            f"{', '.join(r['breaches']) or '-'} | {r['seconds']} |"
        )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", default="", help="comma-separated golden case names")
    parser.add_argument("--out", default="evals/reports/latest.md")
    args = parser.parse_args()

    wanted = {c.strip() for c in args.cases.split(",") if c.strip()}
    paths = sorted(GOLDEN_DIR.glob("*.yaml"))
    if wanted:
        paths = [p for p in paths if p.stem in wanted]
    if not paths:
        print("no golden cases matched", file=sys.stderr)
        return 2

    build_model()  # fail fast if the provider is unreachable/misconfigured
    console = Console()
    records = []
    for path in paths:
        console.print(f"[cyan]eval[/cyan] {path.stem} ...")
        record = run_case(path)
        status = "[green]approved[/green]" if record["approved"] else "[red]rejected[/red]"
        console.print(f"  {status} in {record['seconds']}s")
        records.append(record)

    write_report(records, Path(args.out))
    console.print(f"report written to {args.out}")

    breaches = [b for r in records for b in r["breaches"]]
    if breaches:
        console.print(f"[red]{len(breaches)} deterministic breach(es); failing.[/red]")
        return 1
    approval = sum(1 for r in records if r["approved"]) / len(records)
    minimum = float(os.environ.get("EVAL_MIN_APPROVAL", "0"))
    if approval < minimum:
        console.print(f"[red]approval rate {approval:.0%} below minimum {minimum:.0%}[/red]")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
