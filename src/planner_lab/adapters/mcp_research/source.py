"""ResearchSource adapter for any MCP server exposing `search` and `fetch` tools.

Speaks streamable HTTP via the `mcp` package directly, one `asyncio.run` per
operation (connect -> initialize -> call -> close). That reconnect-per-call
pattern assumes a stateless server and will not work when a caller already
runs inside an event loop; both are fine for this project's CLI and tests.
"""

import asyncio
import json
from datetime import timedelta
from typing import Any

from mcp import ClientSession
from mcp import types as mcp_types
from mcp.client.streamable_http import streamable_http_client

from planner_lab.schemas.results import ResearchDocument, ResearchHit


class ResearchToolError(RuntimeError):
    pass


def _parse_result(result: mcp_types.CallToolResult) -> dict[str, Any]:
    """Extract the payload dict from a tool result.

    Prefers structuredContent; falls back to JSON in the first text block.
    Raises ResearchToolError on the protocol error flag or an application
    "error" key (some servers report errors in normal text with isError unset).
    """
    payload: dict[str, Any] | None = None
    if isinstance(result.structuredContent, dict):
        payload = result.structuredContent
    else:
        for block in result.content:
            if isinstance(block, mcp_types.TextContent):
                try:
                    parsed = json.loads(block.text)
                except json.JSONDecodeError as e:
                    raise ResearchToolError(
                        f"tool returned non-JSON text: {block.text[:200]}"
                    ) from e
                if isinstance(parsed, dict):
                    payload = parsed
                break
    if result.isError:
        detail = json.dumps(payload) if payload else "unknown tool error"
        raise ResearchToolError(f"tool call failed: {detail[:500]}")
    if payload is None:
        raise ResearchToolError("tool returned no parseable payload")
    if "error" in payload:
        raise ResearchToolError(f"tool reported an error: {payload['error']}")
    return payload


class MCPResearchSource:
    name = "mcp"

    def __init__(self, url: str, *, timeout_seconds: float = 30.0):
        self._url = url
        self._timeout = timeout_seconds

    def _call(self, tool: str, arguments: dict[str, Any]) -> dict[str, Any]:
        async def run() -> dict[str, Any]:
            async with streamable_http_client(self._url) as (read, write, _):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    result = await session.call_tool(
                        tool,
                        arguments,
                        read_timeout_seconds=timedelta(seconds=self._timeout),
                    )
                    return _parse_result(result)

        return asyncio.run(run())

    def search(self, query: str, *, limit: int = 5) -> list[ResearchHit]:
        payload = self._call("search", {"query": query})
        results = payload.get("results", [])
        return [
            ResearchHit(ref=str(r["id"]), title=str(r["title"]), url=r.get("url"))
            for r in results[:limit]
        ]

    def fetch(self, ref: str) -> ResearchDocument:
        payload = self._call("fetch", {"id": ref})
        return ResearchDocument(
            ref=str(payload["id"]),
            title=str(payload["title"]),
            text=str(payload["text"]),
            url=payload.get("url"),
            metadata={k: str(v) for k, v in (payload.get("metadata") or {}).items()},
        )
