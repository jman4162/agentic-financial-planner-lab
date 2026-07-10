"""Derive annual cash flow from a transactions CSV. Stdlib only.

Positive amounts are money in, negative are money out. Transfers between the
user's own accounts (category set or payee prefix, per mapping) are excluded
from income and expenses: credit-card payments and brokerage buys are not
spending; spending was already counted at the card/merchant transaction level.

The window is the last 12 complete calendar months ending at the month of the
latest transaction. Fewer complete months are annualized by scaling, with a
warning. Transaction income is post-tax, so it maps to annual_take_home;
annual_gross_income is left unset.

Known limitation: some apps' query-style exports include both split parents
and split children; exact-duplicate rows trigger a warning, but prefer
per-account register exports.
"""

import csv
import datetime
from pathlib import Path

from planner_lab.adapters.csv_import.mapping import ColumnMapping
from planner_lab.schemas.case_file import CashFlow
from planner_lab.schemas.results import CashflowImportResult

_DATE_FORMATS = ("%m/%d/%Y", "%m/%d/%y")
_CURRENCY_CHARS = "$€£"


def _parse_amount(raw: str) -> float:
    """Normalize amount strings: currency symbols, thousands separators,
    parentheses negatives, leading formula-guard apostrophes, empty cells."""
    text = raw.strip().strip('"').lstrip("'").strip()
    if not text:
        return 0.0
    negative = text.startswith("(") and text.endswith(")")
    if negative:
        text = text[1:-1]
    for char in _CURRENCY_CHARS:
        text = text.replace(char, "")
    text = text.replace(",", "").strip()
    if not text:
        return 0.0
    value = float(text)
    return -abs(value) if negative else value


def _parse_date(raw: str) -> datetime.date:
    text = raw.strip().strip('"').lstrip("'")
    try:
        return datetime.date.fromisoformat(text)
    except ValueError:
        pass
    for fmt in _DATE_FORMATS:
        try:
            return datetime.datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"unparseable date {raw!r}; expected ISO or US month/day/year")


def _month_start(day: datetime.date) -> datetime.date:
    return day.replace(day=1)


def _shift_months(day: datetime.date, months: int) -> datetime.date:
    total = day.year * 12 + (day.month - 1) + months
    return datetime.date(total // 12, total % 12 + 1, 1)


class CsvCashflowImporter:
    name = "csv"

    def __init__(self, mapping: ColumnMapping):
        self._mapping = mapping

    def _row_amount(self, row: dict[str, str]) -> float:
        m = self._mapping
        if m.amount is not None:
            return _parse_amount(row[m.amount])
        assert m.inflow is not None and m.outflow is not None
        return _parse_amount(row[m.inflow]) - abs(_parse_amount(row[m.outflow]))

    def _is_transfer(self, row: dict[str, str]) -> bool:
        m = self._mapping
        if m.category is not None:
            category = (row.get(m.category) or "").strip()
            if category in m.transfer_categories:
                return True
        if m.payee is not None and m.transfer_payee_prefixes:
            payee = (row.get(m.payee) or "").strip()
            if payee.startswith(m.transfer_payee_prefixes):
                return True
        return False

    def import_cashflow(self, path: Path) -> CashflowImportResult:
        m = self._mapping
        warnings: list[str] = []
        rows: list[tuple[datetime.date, float, bool, tuple[str, ...]]] = []
        with open(path, encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            headers = reader.fieldnames or []
            missing = [h for h in m.required_headers() if h not in headers]
            if missing:
                raise ValueError(f"CSV is missing expected column(s) {missing}; found {headers}")
            for row in reader:
                raw_date = (row.get(m.date) or "").strip()
                if not raw_date:
                    continue
                day = _parse_date(raw_date)
                amount = self._row_amount(row)
                dedupe_key = tuple(str(row.get(col) or "") for col in headers)
                rows.append((day, amount, self._is_transfer(row), dedupe_key))
        if not rows:
            raise ValueError(f"{path} contains no transactions")

        seen: set[tuple[str, ...]] = set()
        duplicates = 0
        for _, _, _, key in rows:
            if key in seen:
                duplicates += 1
            seen.add(key)
        if duplicates:
            warnings.append(
                f"{duplicates} exact-duplicate row(s) found; split-transaction exports "
                "can double-count. Totals include them; verify the export format."
            )

        latest = max(day for day, _, _, _ in rows)
        window_end = _month_start(latest)  # exclusive: complete months only
        window_start = _shift_months(window_end, -12)
        in_window = [r for r in rows if window_start <= r[0] < window_end]
        if not in_window:
            raise ValueError(
                "no transactions fall inside a complete calendar month; "
                "the export is too short to derive annual cash flow"
            )

        earliest = min(day for day, _, _, _ in in_window)
        months_covered = min(
            (window_end.year * 12 + window_end.month) - (earliest.year * 12 + earliest.month),
            12,
        )

        income = expenses = transfers = 0.0
        for _, amount, is_transfer, _ in in_window:
            if is_transfer:
                transfers += abs(amount)
            elif amount >= 0:
                income += amount
            else:
                expenses += -amount
        if months_covered < 12:
            scale = 12 / months_covered
            income *= scale
            expenses *= scale
            transfers *= scale
            warnings.append(
                f"only {months_covered} complete month(s) of data; totals were "
                f"annualized by scaling with 12/{months_covered}"
            )

        savings = income - expenses
        if savings < 0:
            warnings.append(
                f"expenses exceed income by ${-savings:,.0f}/year; annual_savings recorded as 0"
            )
            savings = 0.0

        return CashflowImportResult(
            cash_flow=CashFlow(
                annual_take_home=round(income, 2),
                annual_expenses=round(expenses, 2),
                annual_savings=round(savings, 2),
            ),
            window_start=window_start,
            window_end=window_end,
            months_covered=months_covered,
            total_inflow=round(income, 2),
            total_outflow=round(expenses, 2),
            excluded_transfer_amount=round(transfers, 2),
            warnings=warnings,
        )
