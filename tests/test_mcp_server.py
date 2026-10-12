import pytest

from market_briefing import mcp_server
from conftest import keyword_embedder


@pytest.fixture(autouse=True)
def use_sample_index(sample_index, monkeypatch):
    monkeypatch.setattr(mcp_server, "_index", sample_index)
    monkeypatch.setattr(mcp_server, "_embedder", lambda: keyword_embedder)


def test_rank_tool_returns_computed_ranking():
    assert mcp_server.rank_movers("down", n=1)[0].startswith("1위 샘플 다운 패딩 오버핏 네이비")


def test_tool_arguments_are_validated():
    with pytest.raises(mcp_server.ToolError):
        mcp_server.rank_movers("sideways")
    with pytest.raises(mcp_server.ToolError):
        mcp_server.search_prices("패딩", k=50)
