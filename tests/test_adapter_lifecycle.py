import pytest

pytest.importorskip("lifecycle_allocation")


class TestLifecycleAllocationEngine:
    def _analyze(self, case=None):  # type: ignore[no-untyped-def]
        from planner_lab.adapters.lifecycle.allocation import LifecycleAllocationEngine
        from tests.support.fixtures import make_case

        case = case or make_case()
        assert case.assumptions is not None
        return LifecycleAllocationEngine().analyze(case, case.assumptions.base)

    def test_findings_keys_and_ranges(self) -> None:
        diag = self._analyze()
        assert diag.engine_name == "lifecycle"
        for key in (
            "alpha_recommended",
            "alpha_star",
            "alpha_unconstrained",
            "human_capital",
            "hw_ratio",
            "gamma",
            "current_stock_pct",
        ):
            assert key in diag.findings
        assert 0 <= diag.findings["alpha_recommended"] <= 1
        assert diag.findings["current_stock_pct"] == 0.7

    def test_diagnostic_note_present(self) -> None:
        diag = self._analyze()
        assert "not a recommendation" in diag.notes[-1]

    def test_zero_wealth_rejected(self) -> None:
        from tests.support.fixtures import make_case

        case = make_case()
        for account in case.balance_sheet.accounts:
            account.balance = 0
        with pytest.raises(ValueError, match="investable assets"):
            self._analyze(case)

    def test_protocol_satisfied(self) -> None:
        from planner_lab.adapters.lifecycle.allocation import LifecycleAllocationEngine
        from planner_lab.protocols import PortfolioAnalyticsEngine

        assert isinstance(LifecycleAllocationEngine(), PortfolioAnalyticsEngine)

    def test_deterministic(self) -> None:
        assert (
            self._analyze().findings["alpha_recommended"]
            == self._analyze().findings["alpha_recommended"]
        )
