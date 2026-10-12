"""market-briefing을 MCP 서버로 노출한다.

Claude Code 같은 MCP 클라이언트가 시세 검색·순위·브리핑 생성을 도구로 쓸 수 있다.
도구 인자는 Function Calling 에이전트와 같은 검증(agent._validate)을 거치고,
브리핑 파일은 서버 설정으로 정한 폴더에만 쓴다.

    MARKET_BRIEFING_INDEX=data/index-stocks python -m market_briefing.mcp_server
"""

from __future__ import annotations

import os
from pathlib import Path

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations

from . import agent, documents, media, retrieval

INDEX_DIR = Path(os.environ.get("MARKET_BRIEFING_INDEX", "data/index"))
OUT_DIR = Path(os.environ.get("MARKET_BRIEFING_OUT", "out"))

mcp = MCPServer(
    name="market-briefing",
    instructions=(
        "시세 데이터(KREAM 스냅샷 또는 국내 주식 종가) 도구. 답변의 숫자는 도구 결과에 있는 값만 쓴다. "
        "순위 질문은 rank_movers, 특정 대상의 흐름은 search_prices를 쓴다."
    ),
)
_index: retrieval.Index | None = None
READ_ONLY = ToolAnnotations(read_only_hint=True, open_world_hint=False)


def index() -> retrieval.Index:
    global _index
    if _index is None:
        _index = retrieval.Index.load(INDEX_DIR)
    return _index


def _call(name: str, args: dict) -> list[str]:
    try:
        clean = agent._validate(name, {k: v for k, v in args.items() if v is not None})
    except agent.ToolError as e:
        raise ToolError(str(e)) from None
    return agent._run(name, clean, index(), embedder=_embedder())


def _embedder():
    from . import models
    return models.embed


@mcp.tool(annotations=READ_ONLY)
def search_prices(query: str, k: int = 4) -> list[str]:
    """질문과 관련된 시세 요약 문서를 유사도 순으로 찾는다(관련도가 낮은 문서는 제외)."""
    return _call("search_prices", {"query": query, "k": k})


@mcp.tool(annotations=READ_ONLY)
def rank_movers(direction: str, keyword: str | None = None, n: int = 3) -> list[str]:
    """관측 기간 변동률 순위. direction은 up 또는 down, keyword로 이름을 거를 수 있다."""
    return _call("rank_movers", {"direction": direction, "keyword": keyword, "n": n})


@mcp.tool(annotations=ToolAnnotations(read_only_hint=False, destructive_hint=False, open_world_hint=False))
def make_briefing(n: int = 3) -> dict:
    """변동 상위 n개로 브리핑 원고·차트·음성·영상을 만들고 파일 경로를 돌려준다(서버 설정 폴더에만 저장)."""
    if not 1 <= n <= 5:
        raise ToolError("n은 1~5")
    docs = [documents.PriceDocument(**{**d, "points": [tuple(p) for p in d["points"]]}) for d in index().docs]
    movers = documents.top_movers(docs, n)
    result = media.render(movers, media.compose_script(movers), OUT_DIR)
    return {"script": result.script, "video": str(result.video), "chart": str(result.chart)}


if __name__ == "__main__":
    mcp.run("stdio")
