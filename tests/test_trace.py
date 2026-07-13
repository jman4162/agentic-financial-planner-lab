from planner_lab.schemas.results import ComputationLedger
from tests.support.fixtures import make_case, make_ledger


class TestLedgerResolve:
    def test_resolves_ledger_output(self) -> None:
        case = make_case()
        ledger = make_ledger(case)
        entry = ledger.entries[0]
        value = ledger.resolve(f"ledger:{entry.entry_id}#funded_ratio", case)
        assert value == entry.outputs["funded_ratio"]

    def test_resolves_case_path(self) -> None:
        case = make_case()
        ledger = ComputationLedger(case_id=case.case_id)
        assert ledger.resolve("case:cash_flow.annual_expenses", case) == 88_000
        assert ledger.resolve("case:balance_sheet.investable_assets", case) == 870_000
        assert ledger.resolve("case:balance_sheet.accounts.0.balance", case) == 350_000
        assert ledger.resolve("case:balance_sheet.accounts[0].balance", case) == 350_000
        assert ledger.resolve("case:household.persons[0].planned_retirement_age", case) == 62

    def test_unresolvable_ids_return_none(self) -> None:
        case = make_case()
        ledger = make_ledger(case)
        assert ledger.resolve("ledger:calc:nope:0001#x", case) is None
        assert ledger.resolve("case:not.a.path", case) is None
        assert ledger.resolve("unknown:scheme", case) is None
        # Fragment-less ref to a multi-output entry is ambiguous.
        assert ledger.resolve(f"ledger:{ledger.entries[0].entry_id}", case) is None

    def test_fragmentless_ref_resolves_single_output_entry(self) -> None:
        case = make_case()
        ledger = make_ledger(case)
        entry_id = ledger.add("sustainable_spending", {}, {"sustainable_spending": 34_800.0})
        assert ledger.resolve(f"ledger:{entry_id}", case) == 34_800.0

    def test_entry_ids_are_sequential_and_kinded(self) -> None:
        case = make_case()
        ledger = ComputationLedger(case_id=case.case_id)
        first = ledger.add("funded_ratio", {}, {"x": 1.0})
        second = ledger.add("simulate", {}, {"p": 0.9}, kind="sim")
        assert first == "calc:funded_ratio:0001"
        assert second == "sim:simulate:0002"
