import datetime
from pathlib import Path

import pytest

from planner_lab.adapters import AdapterUnavailableError, get_cashflow_importer
from planner_lab.adapters.csv_import.importer import (
    CsvCashflowImporter,
    _parse_amount,
    _parse_date,
)
from planner_lab.adapters.csv_import.mapping import PRESETS, ColumnMapping
from planner_lab.protocols import CashflowImporter

DATA = Path(__file__).parent / "data"


class TestParseAmount:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("8000.00", 8000.0),
            ("-2500.00", -2500.0),
            ("-$1,234.56", -1234.56),
            ("$5,000.00", 5000.0),
            ("(89.00)", -89.0),
            ("'-45.00", -45.0),
            ("", 0.0),
            ("  ", 0.0),
            ("€12.50", 12.5),
        ],
    )
    def test_normalizations(self, raw: str, expected: float) -> None:
        assert _parse_amount(raw) == pytest.approx(expected)


class TestParseDate:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("2026-01-05", datetime.date(2026, 1, 5)),
            ("01/05/2026", datetime.date(2026, 1, 5)),
            ("01/05/26", datetime.date(2026, 1, 5)),
        ],
    )
    def test_formats(self, raw: str, expected: datetime.date) -> None:
        assert _parse_date(raw) == expected

    def test_unparseable(self) -> None:
        with pytest.raises(ValueError, match="unparseable date"):
            _parse_date("January the fifth")


class TestMapping:
    def test_amount_xor_pair_enforced(self) -> None:
        with pytest.raises(ValueError, match="not both or neither"):
            ColumnMapping(date="Date")
        with pytest.raises(ValueError, match="not both or neither"):
            ColumnMapping(date="Date", amount="Amount", inflow="In", outflow="Out")

    def test_unknown_preset_rejected(self) -> None:
        with pytest.raises(AdapterUnavailableError, match="generic"):
            get_cashflow_importer("quickbooks")

    def test_protocol_satisfied(self) -> None:
        assert isinstance(CsvCashflowImporter(PRESETS["generic"]), CashflowImporter)


class TestMonarchImport:
    def test_full_year_totals(self) -> None:
        result = get_cashflow_importer("monarch").import_cashflow(
            DATA / "synthetic_transactions_monarch.csv"
        )
        assert result.months_covered == 12
        assert result.window_start == datetime.date(2025, 2, 1)
        assert result.window_end == datetime.date(2026, 2, 1)
        assert result.total_inflow == pytest.approx(96_000.0)
        # 12 x rent 2500 + 12 x groceries 1234.56 + parens 89 + apostrophe 45
        assert result.total_outflow == pytest.approx(44_948.72)
        # 12 x cc payment 3000 + two transfer legs 5000 + buy 2000
        assert result.excluded_transfer_amount == pytest.approx(48_000.0)
        assert result.cash_flow.annual_savings == pytest.approx(51_051.28)
        assert result.warnings == []


class TestYnabImport:
    def test_partial_year_scaled(self) -> None:
        result = get_cashflow_importer("ynab").import_cashflow(
            DATA / "synthetic_transactions_ynab.csv"
        )
        assert result.months_covered == 3
        assert result.total_inflow == pytest.approx(60_000.0)  # 3 x 5000 scaled x4
        assert result.total_outflow == pytest.approx(36_000.0)
        assert result.excluded_transfer_amount == pytest.approx(4_000.0)
        assert any("annualized" in w for w in result.warnings)


class TestActualImport:
    def test_deficit_duplicates_and_transfers(self) -> None:
        result = get_cashflow_importer("actual").import_cashflow(
            DATA / "synthetic_transactions_actual.csv"
        )
        assert result.months_covered == 2
        assert result.total_inflow == pytest.approx(6_000.0)  # 1000 x 6
        assert result.total_outflow == pytest.approx((58.12 * 2 + 2000) * 6)
        assert result.excluded_transfer_amount == pytest.approx(3_000.0)
        assert result.cash_flow.annual_savings == 0.0
        assert any("exceed income" in w for w in result.warnings)
        assert any("duplicate" in w for w in result.warnings)


class TestErrors:
    def test_missing_header(self, tmp_path: Path) -> None:
        bad = tmp_path / "bad.csv"
        bad.write_text("When,HowMuch\n2026-01-01,5\n")
        with pytest.raises(ValueError, match="missing expected column"):
            get_cashflow_importer("generic").import_cashflow(bad)

    def test_empty_file(self, tmp_path: Path) -> None:
        empty = tmp_path / "empty.csv"
        empty.write_text("Date,Amount,Category,Payee\n")
        with pytest.raises(ValueError, match="no transactions"):
            get_cashflow_importer("generic").import_cashflow(empty)

    def test_single_partial_month_rejected(self, tmp_path: Path) -> None:
        short = tmp_path / "short.csv"
        short.write_text("Date,Amount,Category,Payee\n2026-01-05,100.00,Income,Employer\n")
        with pytest.raises(ValueError, match="complete calendar month"):
            get_cashflow_importer("generic").import_cashflow(short)
