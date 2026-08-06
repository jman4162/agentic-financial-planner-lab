import pytest

pytest.importorskip("householdplan")

from planner_lab.protocols import PlanDocumentBuilder  # noqa: E402


def _builder():  # type: ignore[no-untyped-def]
    from planner_lab.adapters.household_plan.builder import HouseholdPlanBuilder

    return HouseholdPlanBuilder()


def _case_and_assumptions():  # type: ignore[no-untyped-def]
    from tests.support.fixtures import make_case

    case = make_case()
    assert case.assumptions is not None
    return case, case.assumptions.base


class TestHouseholdPlanBuilder:
    def test_protocol_satisfied(self) -> None:
        assert isinstance(_builder(), PlanDocumentBuilder)

    def test_builds_a_document_with_the_expected_shape(self) -> None:
        case, assumptions = _case_and_assumptions()
        text = _builder().build(case, assumptions)
        assert text.startswith("# Household financial plan")
        for heading in (
            "## 1. Why",
            "## 2. Goals, in priority order",
            "## 3. Policies",
            "## 4. Action register",
            "## 5. Assumptions",
            "## 6. Review and change policy",
            "## 7. Appendices to write next",
        ):
            assert heading in text
        assert text.rstrip().endswith("Educational, not legal, tax, or investment advice.")

    def test_no_llm_and_no_network_needed(self) -> None:
        """The document is deterministic: same case, same bytes, every time."""
        case, assumptions = _case_and_assumptions()
        builder = _builder()
        assert builder.build(case, assumptions) == builder.build(case, assumptions)

    def test_effective_date_comes_from_the_case_file(self) -> None:
        case, assumptions = _case_and_assumptions()
        assert f"Effective {case.created.isoformat()}" in _builder().build(case, assumptions)

    def test_allocation_is_read_from_the_case_file(self) -> None:
        case, assumptions = _case_and_assumptions()
        text = _builder().build(case, assumptions)
        # 70 stock, with bonds and cash folded together into the other side of the band.
        assert "Target allocation is 70% equities and 30% bonds and cash." in text

    def test_assumption_rationales_come_from_the_assumption_set(self) -> None:
        """The "why this value" column must not read "(fill in)" when the bundle has a
        rationale for the same quantity."""
        case, assumptions = _case_and_assumptions()
        text = _builder().build(case, assumptions)
        row = next(line for line in text.splitlines() if line.startswith("| Investing: Equities"))
        assert assumptions.rationale["expected_return_real"] in row
        assert "_(fill in)_" not in row

    def test_a_value_the_case_file_does_not_imply_is_left_blank(self) -> None:
        """A plausible default in a policy document reads as a decision nobody made."""
        case, assumptions = _case_and_assumptions()
        text = _builder().build(case, assumptions)
        row = next(line for line in text.splitlines() if line.startswith("| Investing: Rebalance"))
        assert "___" in row

    def test_goals_are_ordered_by_priority(self) -> None:
        from planner_lab.schemas.case_file import Goal

        case, assumptions = _case_and_assumptions()
        case.goals = [
            Goal(goal_id="w", kind="purchase", description="Sabbatical", priority="wish"),
            Goal(goal_id="n", kind="emergency_fund", description="Reserve", priority="need"),
            Goal(goal_id="a", kind="other", description="New roof", priority="want"),
        ]
        text = _builder().build(case, assumptions)
        assert "1. **Reserve**" in text
        assert "2. **New roof**" in text
        assert "3. **Sabbatical**" in text

    def test_solo_household_gets_singular_pronouns(self) -> None:
        case, assumptions = _case_and_assumptions()
        assert len(case.household.persons) == 1
        text = _builder().build(case, assumptions)
        assert "## 1. Why I manage money this way" in text
        assert "Partner A and Partner B" not in text

    def test_couple_household_gets_both_names(self) -> None:
        from planner_lab.schemas.case_file import Person

        case, assumptions = _case_and_assumptions()
        case.household.persons.append(
            Person(name="Jordan Example", birth_year=1974, planned_retirement_age=64)
        )
        text = _builder().build(case, assumptions)
        assert "Avery Example and Jordan Example" in text
        assert "## 1. Why we manage money this way" in text

    def test_taxable_account_makes_harvesting_rules_available(self) -> None:
        from planner_lab.adapters.household_plan.builder import case_to_household

        case, _ = _case_and_assumptions()
        assert case_to_household(case).taxable is True

    def test_attribution_is_optional_and_neutral_by_default(self) -> None:
        case, assumptions = _case_and_assumptions()
        builder = _builder()
        assert (
            builder.build(case, assumptions)
            .rstrip()
            .endswith("Educational, not legal, tax, or investment advice.")
        )
        credited = builder.build(case, assumptions, attribution="Drafted with a plan builder.")
        assert credited.rstrip().endswith(
            "Drafted with a plan builder. Educational, not legal, tax, or investment advice."
        )

    def test_check_returns_readable_findings_and_nothing_blocking(self) -> None:
        case, assumptions = _case_and_assumptions()
        findings = _builder().check(case, assumptions)
        assert not [f for f in findings if f.startswith("BLOCKING")]
        assert any("assumptions_justified" in f or "inputs_bound" in f for f in findings)


class TestLoader:
    def test_get_plan_builder_returns_the_adapter(self) -> None:
        from planner_lab.adapters import get_plan_builder

        assert isinstance(get_plan_builder(), PlanDocumentBuilder)

    def test_unknown_builder_name_is_rejected(self) -> None:
        from planner_lab.adapters import AdapterUnavailableError, get_plan_builder

        with pytest.raises(AdapterUnavailableError, match="unknown plan builder"):
            get_plan_builder("nope")
