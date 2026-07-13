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


_RESEARCH_URL_ENV = "PLANNER_LAB_RESEARCH_MCP_URL"


def _research_source_from_env(research: bool) -> Any:
    if not research:
        return None
    import os

    url = os.environ.get(_RESEARCH_URL_ENV)
    if not url:
        console.print(
            f"[red]--research requires the {_RESEARCH_URL_ENV} environment variable.[/red]"
        )
        raise typer.Exit(1)
    from planner_lab.adapters import AdapterUnavailableError, get_research_source

    try:
        return get_research_source(url)
    except AdapterUnavailableError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1) from e


def _load_optional_adapters(health: bool, allocation: bool) -> tuple[Any, Any]:
    from planner_lab.adapters import (
        AdapterUnavailableError,
        get_health_metric,
        get_portfolio_engine,
    )

    try:
        metric = get_health_metric() if health else None
        engine = get_portfolio_engine() if allocation else None
    except AdapterUnavailableError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1) from e
    return metric, engine


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
    research: Annotated[
        bool, typer.Option("--research", help="Fetch cited research from the configured library")
    ] = False,
    health: Annotated[
        bool, typer.Option("--health", help="Compute the fundedness health metric")
    ] = False,
    allocation: Annotated[
        bool, typer.Option("--allocation", help="Run lifecycle allocation diagnostics")
    ] = False,
    ss_comparison: Annotated[
        bool,
        typer.Option("--ss-comparison", help="Compare Social Security claiming ages 62/67/70"),
    ] = False,
    spending_policy: Annotated[
        str,
        typer.Option(
            help="Simulation spending policy: constant_real|guardrails|vpw|floor_ceiling|percent_of_portfolio"
        ),
    ] = "constant_real",
    compare_spending_policies: Annotated[
        bool,
        typer.Option("--compare-spending-policies", help="Simulate every spending policy"),
    ] = False,
    sensitivity: Annotated[
        bool, typer.Option("--sensitivity", help="Which assumptions move the outcome most")
    ] = False,
    trace: Annotated[bool, typer.Option(help="Print OpenTelemetry spans to stdout")] = False,
) -> None:
    """Run the analysis pipeline and print the memo summary and critic report."""
    _models, pipeline = _agent_imports()
    if trace:
        from planner_lab.telemetry import setup_telemetry

        setup_telemetry("console")
    case = load_case(case_path)
    metric, engine = _load_optional_adapters(health, allocation)
    from planner_lab.memo.render import MemoRejectedError

    try:
        result = pipeline.run_analysis(
            case,
            simulate=simulate,
            spending_policy=spending_policy,
            compare_spending_policies=compare_spending_policies,
            sensitivity=sensitivity,
            ss_comparison=ss_comparison,
            research_source=_research_source_from_env(research),
            health_metric=metric,
            portfolio_engine=engine,
            confirm=_confirm_fn(yes),
            n_paths=n_paths,
            seed=seed,
            console=console,
        )
    except MemoRejectedError as e:
        console.print("[red]Memo rejected by the critic after one revision:[/red]")
        _print_report(e.report)
        raise typer.Exit(1) from e
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
    research: Annotated[
        bool, typer.Option("--research", help="Fetch cited research from the configured library")
    ] = False,
    health: Annotated[
        bool, typer.Option("--health", help="Compute the fundedness health metric")
    ] = False,
    allocation: Annotated[
        bool, typer.Option("--allocation", help="Run lifecycle allocation diagnostics")
    ] = False,
    ss_comparison: Annotated[
        bool,
        typer.Option("--ss-comparison", help="Compare Social Security claiming ages 62/67/70"),
    ] = False,
    spending_policy: Annotated[
        str,
        typer.Option(
            help="Simulation spending policy: constant_real|guardrails|vpw|floor_ceiling|percent_of_portfolio"
        ),
    ] = "constant_real",
    compare_spending_policies: Annotated[
        bool,
        typer.Option("--compare-spending-policies", help="Simulate every spending policy"),
    ] = False,
    sensitivity: Annotated[
        bool, typer.Option("--sensitivity", help="Which assumptions move the outcome most")
    ] = False,
) -> None:
    """Run the pipeline and write a critic-approved markdown memo plus an audit sidecar."""
    from planner_lab.memo.render import MemoRejectedError, render_markdown

    _models, pipeline = _agent_imports()
    case = load_case(case_path)
    metric, engine = _load_optional_adapters(health, allocation)
    try:
        result = pipeline.run_analysis(
            case,
            simulate=simulate,
            spending_policy=spending_policy,
            compare_spending_policies=compare_spending_policies,
            sensitivity=sensitivity,
            ss_comparison=ss_comparison,
            research_source=_research_source_from_env(research),
            health_metric=metric,
            portfolio_engine=engine,
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


@app.command("import-cashflow")
def import_cashflow(
    csv_path: Annotated[Path, typer.Argument(exists=True, dir_okay=False)],
    fmt: Annotated[
        str, typer.Option("--format", help="CSV preset: generic|monarch|actual|ynab")
    ] = "generic",
    case_path: Annotated[
        Path | None, typer.Option("--case", help="Case file to compare or update")
    ] = None,
    write: Annotated[
        bool, typer.Option("--write", help="Write the derived cash flow into --case")
    ] = False,
) -> None:
    """Derive annual cash flow from a transactions CSV export."""
    from planner_lab.adapters import AdapterUnavailableError, get_cashflow_importer

    try:
        importer = get_cashflow_importer(fmt)
    except AdapterUnavailableError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1) from e
    result = importer.import_cashflow(csv_path)

    table = Table(show_header=False, title=f"Cash flow derived from {csv_path.name}")
    table.add_row("Window", f"{result.window_start} to {result.window_end} (exclusive)")
    table.add_row("Complete months", str(result.months_covered))
    table.add_row("Income (take-home)", f"${result.total_inflow:,.0f}/yr")
    table.add_row("Expenses", f"${result.total_outflow:,.0f}/yr")
    table.add_row("Savings", f"${result.cash_flow.annual_savings or 0:,.0f}/yr")
    table.add_row("Excluded transfers", f"${result.excluded_transfer_amount:,.0f}/yr")
    console.print(table)
    for warning in result.warnings:
        console.print(f"[yellow]warning:[/yellow] {warning}")

    if case_path is None:
        if write:
            console.print("[red]--write requires --case.[/red]")
            raise typer.Exit(1)
        return
    case = load_case(case_path)
    console.print("\nCase file cash flow (current -> imported):")
    for field in ("annual_take_home", "annual_expenses", "annual_savings"):
        old = getattr(case.cash_flow, field)
        new = getattr(result.cash_flow, field)
        old_text = f"${old:,.0f}" if old is not None else "unset"
        new_text = f"${new:,.0f}" if new is not None else "unset"
        console.print(f"  {field}: {old_text} -> {new_text}")
    if write:
        case.cash_flow = result.cash_flow
        case = type(case).model_validate(case.model_dump(mode="json"))
        save_case(case, case_path)
        console.print(f"[green]Case file updated:[/green] {case_path}")


@app.command()
def intake(
    output: Annotated[Path, typer.Option("-o", "--output", help="Where to save the case file")],
    session_id: Annotated[str | None, typer.Option(help="Resumable session id")] = None,
) -> None:
    """Interactive intake chat. Type 'done' to save the case file and exit."""
    import os

    _models, _pipeline = _agent_imports()
    from planner_lab.agents.models import build_model
    from planner_lab.agents.orchestrator import build_orchestrator

    agent, state = build_orchestrator(
        build_model(),
        session_id=session_id,
        research_url=os.environ.get(_RESEARCH_URL_ENV),
    )
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
