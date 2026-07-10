"""In-memory Protocol implementations for pipeline tests. No network, no extras."""

from planner_lab.schemas.assumptions import AssumptionSet
from planner_lab.schemas.case_file import CaseFile
from planner_lab.schemas.results import (
    MetricResult,
    PortfolioDiagnostics,
    ResearchDocument,
    ResearchHit,
)


class FakeResearchSource:
    name = "fake"

    def __init__(self, hits: list[ResearchHit], docs: dict[str, ResearchDocument]):
        self._hits = hits
        self._docs = docs
        self.search_calls: list[str] = []
        self.fetch_calls: list[str] = []

    def search(self, query: str, *, limit: int = 5) -> list[ResearchHit]:
        self.search_calls.append(query)
        return self._hits[:limit]

    def fetch(self, ref: str) -> ResearchDocument:
        self.fetch_calls.append(ref)
        return self._docs[ref]


def make_fake_research_source() -> FakeResearchSource:
    doc = ResearchDocument(
        ref="doc-1",
        title="Withdrawal rates explained",
        text="Long educational text about withdrawal rates. " * 200,
        url="https://example.com/doc-1",
        metadata={"category": "strategy"},
    )
    return FakeResearchSource(
        hits=[ResearchHit(ref="doc-1", title=doc.title, url=doc.url)],
        docs={"doc-1": doc},
    )


class FakeHealthMetric:
    name = "fake-metric"

    def compute(self, case: CaseFile, assumptions: AssumptionSet) -> MetricResult:
        return MetricResult(
            metric_name="cefr",
            value=1.4,
            components={"net_assets": 700_000.0, "liability_pv": 500_000.0},
            interpretation="Strong",
        )


class FakePortfolioEngine:
    name = "fake-engine"

    def analyze(self, case: CaseFile, assumptions: AssumptionSet) -> PortfolioDiagnostics:
        return PortfolioDiagnostics(
            engine_name="fake-engine",
            findings={"alpha_recommended": 0.72, "alpha_star": 0.55, "hw_ratio": 1.8},
            notes=["Model output.", "Diagnostic comparison only, not a recommendation."],
        )
