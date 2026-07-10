import json
import os
from typing import Any

import pytest

mcp_types = pytest.importorskip("mcp.types")


def make_result(
    *,
    structured: dict[str, Any] | None = None,
    text: str | None = None,
    is_error: bool = False,
) -> Any:
    content = [mcp_types.TextContent(type="text", text=text)] if text is not None else []
    return mcp_types.CallToolResult(content=content, structuredContent=structured, isError=is_error)


class TestParseResult:
    def test_prefers_structured_content(self) -> None:
        from planner_lab.adapters.mcp_research.source import _parse_result

        result = make_result(structured={"results": []}, text='{"results": ["ignored"]}')
        assert _parse_result(result) == {"results": []}

    def test_falls_back_to_text_json(self) -> None:
        from planner_lab.adapters.mcp_research.source import _parse_result

        result = make_result(text=json.dumps({"id": "x", "title": "T"}))
        assert _parse_result(result)["id"] == "x"

    def test_is_error_flag_raises(self) -> None:
        from planner_lab.adapters.mcp_research.source import ResearchToolError, _parse_result

        with pytest.raises(ResearchToolError, match="tool call failed"):
            _parse_result(make_result(text='{"detail": "boom"}', is_error=True))

    def test_error_key_in_payload_raises(self) -> None:
        from planner_lab.adapters.mcp_research.source import ResearchToolError, _parse_result

        result = make_result(text='{"error": "No guide found for id \'nope\'."}')
        with pytest.raises(ResearchToolError, match="No guide found"):
            _parse_result(result)

    def test_non_json_text_raises(self) -> None:
        from planner_lab.adapters.mcp_research.source import ResearchToolError, _parse_result

        with pytest.raises(ResearchToolError, match="non-JSON"):
            _parse_result(make_result(text="<html>oops</html>"))


class TestMapping:
    def _source_with_canned(self, payloads: dict[str, dict[str, Any]]) -> Any:
        from planner_lab.adapters.mcp_research.source import MCPResearchSource

        source = MCPResearchSource("http://unused.invalid/mcp")
        source._call = lambda tool, arguments: payloads[tool]  # type: ignore[method-assign]
        return source

    def test_search_maps_hits_and_limits(self) -> None:
        source = self._source_with_canned(
            {
                "search": {
                    "results": [
                        {"id": f"guide-{i}", "title": f"Guide {i}", "url": f"https://x/{i}"}
                        for i in range(8)
                    ]
                }
            }
        )
        hits = source.search("withdrawal", limit=3)
        assert [h.ref for h in hits] == ["guide-0", "guide-1", "guide-2"]
        assert hits[0].title == "Guide 0"

    def test_fetch_maps_document(self) -> None:
        source = self._source_with_canned(
            {
                "fetch": {
                    "id": "guide-1",
                    "title": "Guide 1",
                    "text": "body text",
                    "url": "https://x/1",
                    "metadata": {"category": "strategy", "readingTime": 15},
                }
            }
        )
        doc = source.fetch("guide-1")
        assert doc.ref == "guide-1"
        assert doc.metadata == {"category": "strategy", "readingTime": "15"}

    def test_protocol_satisfied(self) -> None:
        from planner_lab.adapters.mcp_research.source import MCPResearchSource
        from planner_lab.protocols import ResearchSource

        assert isinstance(MCPResearchSource("http://unused.invalid/mcp"), ResearchSource)


@pytest.mark.network
@pytest.mark.skipif(
    not os.environ.get("PLANNER_LAB_RESEARCH_MCP_URL"),
    reason="PLANNER_LAB_RESEARCH_MCP_URL not set",
)
class TestLiveServer:
    def test_search_and_fetch_round_trip(self) -> None:
        from planner_lab.adapters.mcp_research.source import MCPResearchSource

        source = MCPResearchSource(os.environ["PLANNER_LAB_RESEARCH_MCP_URL"])
        hits = source.search("safe withdrawal rate", limit=3)
        assert hits
        doc = source.fetch(hits[0].ref)
        assert doc.ref == hits[0].ref
        assert len(doc.text) > 500
