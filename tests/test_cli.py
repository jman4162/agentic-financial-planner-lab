from pathlib import Path

from typer.testing import CliRunner

from planner_lab.cli import app

runner = CliRunner()
EXAMPLES = Path(__file__).parent.parent / "examples" / "cases"


class TestValidate:
    def test_valid_case(self) -> None:
        result = runner.invoke(app, ["validate", str(EXAMPLES / "sample_household.yaml")])
        assert result.exit_code == 0
        assert "sample-household" in result.output
        assert "No material fields missing" in result.output

    def test_incomplete_case_lists_gaps(self) -> None:
        result = runner.invoke(app, ["validate", str(EXAMPLES / "incomplete_household.yaml")])
        assert result.exit_code == 0
        assert "Missing material fields" in result.output
        assert "cash_flow.annual_expenses" in result.output

    def test_invalid_yaml_fails(self, tmp_path: Path) -> None:
        bad = tmp_path / "bad.yaml"
        bad.write_text("case_id: only-an-id\n")
        result = runner.invoke(app, ["validate", str(bad)])
        assert result.exit_code == 1


class TestCalc:
    def test_funded_ratio(self) -> None:
        result = runner.invoke(
            app,
            ["calc", "funded-ratio", "--portfolio", "900000", "--spending", "50000"],
        )
        assert result.exit_code == 0
        assert "0.72" in result.output
        assert "1,250,000" in result.output

    def test_fi_timeline(self) -> None:
        result = runner.invoke(
            app,
            [
                "calc",
                "fi-timeline",
                "--portfolio",
                "250000",
                "--savings",
                "100000",
                "--spending",
                "50000",
                "--real-return",
                "0.0",
            ],
        )
        assert result.exit_code == 0
        assert "10.0" in result.output

    def test_fi_timeline_unreachable(self) -> None:
        result = runner.invoke(
            app,
            [
                "calc",
                "fi-timeline",
                "--portfolio",
                "0",
                "--savings",
                "0",
                "--spending",
                "50000",
            ],
        )
        assert result.exit_code == 0
        assert "unreachable" in result.output
