"""Column mappings for transaction-CSV exports from common budgeting apps.

Header names are community-documented conventions; the importer matches by
header name, never by position. Transfers between the user's own accounts are
excluded from income/expense totals via category names or payee prefixes,
following each app's own cash-flow convention.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ColumnMapping:
    date: str
    amount: str | None = None  # single signed column, XOR the inflow/outflow pair
    inflow: str | None = None
    outflow: str | None = None
    category: str | None = None
    account: str | None = None
    payee: str | None = None
    transfer_categories: frozenset[str] = field(default_factory=frozenset)
    transfer_payee_prefixes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        has_amount = self.amount is not None
        has_pair = self.inflow is not None and self.outflow is not None
        if has_amount == has_pair:
            raise ValueError(
                "mapping needs either a signed 'amount' column or an "
                "inflow/outflow pair, not both or neither"
            )

    def required_headers(self) -> list[str]:
        headers = [self.date]
        headers += [c for c in (self.amount, self.inflow, self.outflow) if c is not None]
        return headers


PRESETS: dict[str, ColumnMapping] = {
    "generic": ColumnMapping(date="Date", amount="Amount", category="Category", payee="Payee"),
    "monarch": ColumnMapping(
        date="Date",
        amount="Amount",
        category="Category",
        account="Account",
        payee="Merchant",
        transfer_categories=frozenset({"Transfer", "Credit Card Payment", "Buy", "Sell"}),
    ),
    "actual": ColumnMapping(
        date="Date",
        amount="Amount",
        category="Category",
        account="Account",
        payee="Payee",
        transfer_payee_prefixes=("Transfer",),
    ),
    "ynab": ColumnMapping(
        date="Date",
        inflow="Inflow",
        outflow="Outflow",
        category="Category",
        account="Account",
        payee="Payee",
        transfer_payee_prefixes=("Transfer : ",),
    ),
}
