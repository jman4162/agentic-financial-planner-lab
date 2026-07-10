from pathlib import Path

import pytest
from pydantic import ValidationError

from planner_lab.case_io import load_case, save_case
from planner_lab.schemas.case_file import CaseFile, Portfolio
from tests.support.fixtures import make_case

EXAMPLES = Path(__file__).parent.parent / "examples" / "cases"


class TestCaseFile:
    def test_round_trip(self) -> None:
        case = make_case()
        rebuilt = CaseFile.model_validate(case.model_dump())
        assert rebuilt == case

    def test_yaml_round_trip(self, tmp_path: Path) -> None:
        case = make_case()
        path = tmp_path / "case.yaml"
        save_case(case, path)
        assert load_case(path) == case

    def test_sample_fixture_loads_with_no_gaps(self) -> None:
        case = load_case(EXAMPLES / "sample_household.yaml")
        assert case.case_id == "sample-household"
        assert case.missing_fields == []
        assert case.balance_sheet.investable_assets == 980_000
        assert case.balance_sheet.net_worth == 840_000

    def test_incomplete_fixture_flags_gaps(self) -> None:
        case = load_case(EXAMPLES / "incomplete_household.yaml")
        assert "cash_flow.annual_expenses" in case.missing_fields
        assert "cash_flow.annual_savings" in case.missing_fields
        assert "portfolio" in case.missing_fields
        assert "goals.retirement.annual_amount_today" in case.missing_fields

    def test_effective_savings_derived(self) -> None:
        case = make_case()
        case.cash_flow.annual_savings = None
        assert case.cash_flow.effective_savings() == 50_000


class TestPortfolio:
    def test_rejects_weights_not_summing_to_one(self) -> None:
        with pytest.raises(ValidationError):
            Portfolio(stock_pct=0.7, bond_pct=0.7)

    def test_accepts_valid_weights(self) -> None:
        p = Portfolio(stock_pct=0.6, bond_pct=0.4)
        assert p.cash_pct == 0


class TestValidation:
    def test_negative_balance_rejected(self) -> None:
        case = make_case()
        data = case.model_dump()
        data["balance_sheet"]["accounts"][0]["balance"] = -5
        with pytest.raises(ValidationError):
            CaseFile.model_validate(data)

    def test_household_requires_a_person(self) -> None:
        case = make_case()
        data = case.model_dump()
        data["household"]["persons"] = []
        with pytest.raises(ValidationError):
            CaseFile.model_validate(data)
