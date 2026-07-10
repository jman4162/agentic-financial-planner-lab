"""planner-lab command-line interface."""

import json
import math
import sys
from pathlib import Path
from typing import Annotated, Any

import typer
from rich.console import Console
from rich.table import Table

from planner_lab import calculators
from planner_lab.case_io import load_case, save_case

app = typer.Typer(help="Auditable financial planning workflows.", no_args_is_help=True)
calc_app = typer.Typer(help="Run a deterministic calculator.", no_args_is_help=True)
app.add_typer(calc_app, name="calc")

console = Console()


def _agent_imports() -> Any:
    try:
        from planner_lab.agents import models, pipeline
    except ImportError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1) from e
    return models, pipeline


def _confirm_fn(yes: bool) -> Any:
    if yes:
        return lambda _prompt: True
    if not sys.stdin.isatty():
        console.print("[red]Non-interactive run: pass --yes to accept the assumptions.[/red]")
        raise typer.Exit(1)
    return typer.confirm


def _print_report(report: Any) -> None:
    console.print("\nCritic checks:")
    for check in report.checks:
        color = "green" if check.passed else "red"
        status = "pass" if check.passed else "FAIL"
        console.print(f"  [{color}]{status}[/{color}] {check.check_id}: {check.details}")


@app.command()
def validate(case_path: Annotated[Path, typer.Argument(exists=True, dir_okay=False)]) -> None:
    """Validate a case file and report material gaps."""
    try:
        case = load_case(case_path)
    except Exception as e:
        console.print(f"[red]Invalid case file:[/red] {e}")
        raise typer.Exit(1) from e
    console.print(f"[green]Valid case file:[/green] {case.case_id}")
    console.print(f"Question: {case.question}")
    console.print(f"Net worth: ${case.balance_sheet.net_worth:,.0f}")
    console.print(f"Investable assets: ${case.balance_sheet.investable_assets:,.0f}")
    if case.missing_fields:
        console.print("[yellow]Missing material fields:[/yellow]")
        for field in case.missing_fields:
            console.print(f"  - {field}")
    else:
        console.print("[green]No material fields missing.[/green]")


@calc_app.command("funded-ratio")
def calc_funded_ratio(
    portfolio: Annotated[float, typer.Option(help="Current investable assets, dollars")],
    spending: Annotated[float, typer.Option(help="Target annual spending, dollars")],
    withdrawal_rate: Annotated[float, typer.Option(help="Withdrawal rate, decimal")] = 0.04,
) -> None:
    """Funded ratio: portfolio vs capital needed for the spending target."""
    result = calculators.funded_ratio(portfolio, spending, withdrawal_rate)
    table = Table(show_header=False)
    table.add_row("Funded ratio", f"{result['funded_ratio']:.2f}")
    table.add_row("Required capital", f"${result['required_capital']:,.0f}")
    table.add_row("Withdrawal rate", f"{result['withdrawal_rate']:.1%}")
    console.print(table)


@calc_app.command("fi-timeline")
def calc_fi_timeline(
    portfolio: Annotated[float, typer.Option(help="Current investable assets, dollars")],
    savings: Annotated[float, typer.Option(help="Annual savings, dollars")],
    spending: Annotated[float, typer.Option(help="Target annual spending, dollars")],
    real_return: Annotated[float, typer.Option(help="Expected real return, decimal")] = 0.04,
    withdrawal_rate: Annotated[float, typer.Option(help="Withdrawal rate, decimal")] = 0.04,
) -> None:
    """Years until the portfolio supports the spending target."""
    years = calculators.years_to_fi(portfolio, savings, spending, real_return, withdrawal_rate)
    if math.isinf(years):
        console.print("[yellow]Target is unreachable with these inputs.[/yellow]")
        raise typer.Exit(0)
    console.print(f"Years to financial independence: {years:.1f}")


@app.command()
def analyze(
    case_path: Annotated[Path, typer.Argument(exists=True, dir_okay=False)],
    simulate: Annotated[bool, typer.Option(help="Run Monte Carlo simulation")] = False,
    yes: Annotated[
        bool, typer.Option("--yes", help="Accept assumptions without prompting")
    ] = False,
    n_paths: Annotated[int, typer.Option(help="Simulation paths")] = 2000,
    seed: Annotated[int, typer.Option(help="Simulation seed")] = 42,
    trace: Annotated[bool, typer.Option(help="Print OpenTelemetry spans to stdout")] = False,
) -> None:
    """Run the analysis pipeline and print the memo summary and critic report."""
    _models, pipeline = _agent_imports()
    if trace:
        from planner_lab.telemetry import setup_telemetry

        setup_telemetry("console")
    case = load_case(case_path)
    result = pipeline.run_analysis(
        case,
        simulate=simulate,
        confirm=_confirm_fn(yes),
        n_paths=n_paths,
        seed=seed,
        console=console,
    )
    console.print(f"\n[bold]Executive summary[/bold]\n{result.memo.executive_summary}")
    for number in result.memo.all_traced_numbers():
        console.print(f"  {number.label}: {number.value} (source: {number.source_id})")
    _print_report(result.report)


@app.command()
def memo(
    case_path: Annotated[Path, typer.Argument(exists=True, dir_okay=False)],
    output: Annotated[Path, typer.Option("-o", "--output", help="Output markdown path")],
    simulate: Annotated[bool, typer.Option(help="Run Monte Carlo simulation")] = False,
    yes: Annotated[
        bool, typer.Option("--yes", help="Accept assumptions without prompting")
    ] = False,
    n_paths: Annotated[int, typer.Option(help="Simulation paths")] = 2000,
    seed: Annotated[int, typer.Option(help="Simulation seed")] = 42,
) -> None:
    """Run the pipeline and write a critic-approved markdown memo plus an audit sidecar."""
    from planner_lab.memo.render import MemoRejectedError, render_markdown

    _models, pipeline = _agent_imports()
    case = load_case(case_path)
    try:
        result = pipeline.run_analysis(
            case,
            simulate=simulate,
            confirm=_confirm_fn(yes),
            n_paths=n_paths,
            seed=seed,
            console=console,
        )
    except MemoRejectedError as e:
        console.print("[red]Memo rejected by the critic after one revision:[/red]")
        _print_report(e.report)
        raise typer.Exit(1) from e
    output.write_text(render_markdown(result.memo, result.report))
    audit_path = output.with_suffix(".audit.json")
    audit_path.write_text(
        json.dumps(
            {
                "memo": result.memo.model_dump(mode="json"),
                "critic_report": result.report.model_dump(mode="json"),
                "ledger": result.ledger.model_dump(mode="json"),
            },
            indent=2,
        )
    )
    console.print(f"[green]Memo written:[/green] {output}")
    console.print(f"[green]Audit sidecar:[/green] {audit_path}")
    _print_report(result.report)


@app.command()
def intake(
    output: Annotated[Path, typer.Option("-o", "--output", help="Where to save the case file")],
    session_id: Annotated[str | None, typer.Option(help="Resumable session id")] = None,
) -> None:
    """Interactive intake chat. Type 'done' to save the case file and exit."""
    _models, _pipeline = _agent_imports()
    from planner_lab.agents.models import build_model
    from planner_lab.agents.orchestrator import build_orchestrator

    agent, state = build_orchestrator(build_model(), session_id=session_id)
    console.print(
        "[bold]Planning intake.[/bold] Describe your question; type 'done' to save and exit."
    )
    while True:
        try:
            line = console.input("[cyan]you>[/cyan] ")
        except (EOFError, KeyboardInterrupt):
            break
        if line.strip().lower() in {"done", "exit", "quit"}:
            break
        if not line.strip():
            continue
        agent(line)
    save_case(state.case, output)
    console.print(f"[green]Case file saved:[/green] {output}")
    if state.case.missing_fields:
        console.print(f"Missing material fields: {', '.join(state.case.missing_fields)}")


if __name__ == "__main__":
    app()
