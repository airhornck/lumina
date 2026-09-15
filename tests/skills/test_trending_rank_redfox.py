"""Phase 3 P1 TDD Harness：TrendingRank Redfox 数据采集 Red 状态测试。"""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


pytestmark = pytest.mark.asyncio


async def _async_iter(pieces):
    for piece in pieces:
        yield piece


def _mock_llm_client(pieces):
    mock_client = AsyncMock()
    mock_client.stream_completion = MagicMock(return_value=_async_iter(pieces))
    mock_client.config.api_key = "test-key"
    return mock_client


async def test_redfox_client_is_configured():
    from orchestra.skills.trending_rank import redfox_client

    with patch.dict("os.environ", {"REDFOX_API_KEY": "test-key", "REDFOX_API_BASE_URL": "https://api.redfox.test"}):
        client = redfox_client.RedfoxClient()
        assert client.api_key == "test-key"
        assert client.base_url == "https://api.redfox.test"


async def test_redfox_client_not_configured():
    from orchestra.skills.trending_rank import redfox_client

    with patch.dict("os.environ", {"REDFOX_API_KEY": "", "REDFOX_API_BASE_URL": ""}, clear=False):
        client = redfox_client.RedfoxClient()
        assert not client.is_configured()


async def test_redfox_client_fetch_trending_success():
    from orchestra.skills.trending_rank import redfox_client

    with patch.dict("os.environ", {"REDFOX_API_KEY": "test-key"}):
        client = redfox_client.RedfoxClient()
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            "items": [
                {"title": "爆款1", "platform": "douyin", "metrics": {"likes": 10000, "comments": 100, "collections": 500, "shares": 100, "views": 100000}},
            ]
        })
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_session.get = MagicMock(return_value=mock_response)

        with patch("aiohttp.ClientSession") as MockSession:
            MockSession.return_value = mock_session
            result = await client.fetch_trending("护肤", platform="douyin", time_window="7d", limit=10)

    assert result["ok"] is True
    assert len(result["items"]) == 1
    assert result["items"][0]["title"] == "爆款1"


async def test_keyword_expansion():
    from orchestra.skills.trending_rank import keyword_expand

    with patch.object(keyword_expand, "get_client", return_value=_mock_llm_client(['["护肤","skincare","成分党","平价护肤","敏感肌","早C晚A"]'])):
        with patch.object(keyword_expand, "get_hub", return_value=AsyncMock()):
            result = await keyword_expand.expand_keywords("护肤")

    assert isinstance(result, list)
    assert "护肤" in result
    assert "成分党" in result


async def test_engagement_rate_calculation():
    from orchestra.skills.trending_rank import rank_engine

    item = {
        "metrics": {"likes": 1000, "comments": 100, "collections": 200, "shares": 50, "views": 10000},
    }
    rate = rank_engine.calculate_engagement_rate(item)
    # (1000*1 + 100*3 + 200*2 + 50*4) / 10000 = (1000 + 300 + 400 + 200) / 10000 = 0.19
    assert rate == pytest.approx(0.19)


async def test_deduplicate_items():
    from orchestra.skills.trending_rank import rank_engine

    items = [
        {"title": "爆款标题", "platform": "douyin", "engagement_rate": 0.1},
        {"title": "爆款标题", "platform": "xiaohongshu", "engagement_rate": 0.2},
        {"title": "另一个标题", "platform": "douyin", "engagement_rate": 0.15},
    ]
    result = rank_engine.deduplicate_items(items)
    assert len(result) == 2
    titles = [r["title"] for r in result]
    assert "爆款标题" in titles
    assert "另一个标题" in titles


async def test_trending_rank_skill_with_redfox():
    from orchestra.skills.trending_rank import skill as trending_rank_skill

    mock_redfox_result = {
        "ok": True,
        "data_source": "redfox",
        "items": [
            {"title": "护肤爆款", "platform": "douyin", "author": "作者A", "metrics": {"likes": 10000, "comments": 100, "collections": 500, "shares": 100, "views": 100000}, "tags": ["护肤"]},
        ],
        "expanded_keywords": ["护肤", "成分党"],
        "hot_keywords": ["早C晚A"],
    }

    with patch.object(trending_rank_skill, "redfox_client") as mock_redfox_module:
        MockClient = mock_redfox_module.RedfoxClient
        instance = MockClient.return_value
        instance.is_configured = MagicMock(return_value=True)
        instance.fetch_trending = AsyncMock(return_value=mock_redfox_result)

        with patch.object(trending_rank_skill, "get_client", return_value=_mock_llm_client(["这是爆款分析摘要"])):
            with patch.object(trending_rank_skill, "get_hub", return_value=AsyncMock()):
                result = await trending_rank_skill.run(
                    message="查一下护肤的爆款榜单",
                    platform="xiaohongshu",
                    context={},
                    history=[],
                )

    assert isinstance(result, str)
    assert "护肤爆款" in result


async def test_trending_rank_skill_fallback_when_redfox_unconfigured():
    from orchestra.skills.trending_rank import skill as trending_rank_skill

    with patch.object(trending_rank_skill, "redfox_client") as mock_redfox_module:
        MockClient = mock_redfox_module.RedfoxClient
        instance = MockClient.return_value
        instance.is_configured = MagicMock(return_value=False)

        with patch.object(trending_rank_skill, "get_client", return_value=_mock_llm_client([" fallback 榜单"])):
            with patch.object(trending_rank_skill, "get_hub", return_value=AsyncMock()):
                result = await trending_rank_skill.run(
                    message="查爆款",
                    platform="xiaohongshu",
                    context={},
                    history=[],
                )

    assert isinstance(result, str)
