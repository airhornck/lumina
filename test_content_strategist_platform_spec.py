"""
深度验证：skill-content-strategist 的各工具是否正确接入平台规范库
"""
import asyncio
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT / "packages" / "knowledge-base" / "src"))
sys.path.insert(0, str(PROJECT_ROOT / "packages" / "lumina-skills" / "src"))
sys.path.insert(0, str(PROJECT_ROOT / "skills" / "skill-content-strategist" / "src"))
sys.path.insert(0, str(PROJECT_ROOT / "apps" / "rpa" / "src"))

from skill_content_strategist.main import (  # noqa: E402
    analyze_positioning,
    generate_topic_calendar,
    predict_trends,
    analyze_competitor_real,
    PositioningInput,
    TopicCalendarInput,
)
from lumina_skills import llm_utils  # noqa: E402

original_call_llm = llm_utils.call_llm


def _mock_factory():
    captured = {}

    async def mock(*, prompt, **kwargs):
        captured["prompt"] = prompt
        return kwargs.get("fallback_response", {"content": prompt})

    return mock, captured


async def test_analyze_positioning():
    mock, captured = _mock_factory()
    llm_utils.call_llm = mock
    try:
        await analyze_positioning(
            PositioningInput(platform="xiaohongshu", niche="美妆", user_id="u1")
        )
    finally:
        llm_utils.call_llm = original_call_llm

    prompt = captured["prompt"]
    assert "hook_position" in prompt or "title_length" in prompt, (
        "analyze_positioning prompt 中未注入平台 DNA 规范"
    )
    assert "medical类禁用词" in prompt, "analyze_positioning prompt 中未注入审核规则"
    assert "平台 DNA 规范（来自平台规范库）" in prompt, "analyze_positioning prompt 缺少规范标题"
    print("[PASS] analyze_positioning 已接入平台规范库")
    return True


async def test_generate_topic_calendar():
    mock, captured = _mock_factory()
    llm_utils.call_llm = mock
    try:
        await generate_topic_calendar(
            TopicCalendarInput(platform="douyin", niche="数码", positioning="专业评测", user_id="u1")
        )
    finally:
        llm_utils.call_llm = original_call_llm

    prompt = captured["prompt"]
    assert "hook_position" in prompt, "generate_topic_calendar prompt 中未注入平台 DNA 规范"
    assert "medical类禁用词" in prompt, "generate_topic_calendar prompt 中未注入审核规则"
    assert "选题需避开平台审核禁用词" in prompt, "generate_topic_calendar 未要求结合审核规则"
    print("[PASS] generate_topic_calendar 已接入平台规范库")
    return True


async def test_predict_trends():
    mock, captured = _mock_factory()
    llm_utils.call_llm = mock
    try:
        await predict_trends(niche="健身", platform="bilibili", user_id="u1")
    finally:
        llm_utils.call_llm = original_call_llm

    prompt = captured["prompt"]
    assert "opening" in prompt or "前30秒交代价值点" in prompt, (
        "predict_trends prompt 中未注入 bilibili 平台 DNA 规范"
    )
    assert "sensitive类禁用词" in prompt, "predict_trends prompt 中未注入审核规则"
    assert "结合平台 DNA" in prompt, "predict_trends 未要求结合平台 DNA"
    print("[PASS] predict_trends 已接入平台规范库")
    return True


async def test_analyze_competitor_real():
    # 该函数 LLM 分析在 RPA 成功后才会触发，RPA 会失败，我们用 monkey-patch 让 RPA 成功
    class FakeResult:
        success = True
        error = None
        data = {
            "nickname": "测试竞品",
            "bio": "bio",
            "followers": 1000,
            "following": 100,
            "likes": 5000,
            "content_count": 50,
            "diagnosis": {"account_gene": {"content_types": ["视频"], "style_tags": ["搞笑"]}, "health_score": 80, "key_issues": []},
            "recent_contents": [{"title": "T1"}, {"title": "T2"}],
            "crawled_at": "2024-01-01",
        }

    class FakeRPA:
        async def crawl_account(self, **kwargs):
            return FakeResult()

    import rpa.skill_utils as rpa_mod
    original_get_rpa_helper = rpa_mod.get_rpa_helper
    rpa_mod.get_rpa_helper = lambda: FakeRPA()

    mock, captured = _mock_factory()
    llm_utils.call_llm = mock
    try:
        await analyze_competitor_real("fake_id", platform="xiaohongshu", user_id="u1")
    finally:
        llm_utils.call_llm = original_call_llm
        rpa_mod.get_rpa_helper = original_get_rpa_helper

    prompt = captured.get("prompt", "")
    assert "hook_position" in prompt or "title_length" in prompt, (
        "analyze_competitor_real prompt 中未注入平台 DNA 规范"
    )
    assert "medical类禁用词" in prompt, "analyze_competitor_real prompt 中未注入审核规则"
    assert "结合平台 DNA 与定位方法论评估内容适配度" in prompt, (
        "analyze_competitor_real 未要求结合平台 DNA"
    )
    print("[PASS] analyze_competitor_real 已接入平台规范库")
    return True


async def main():
    print("=" * 60)
    print("验证 skill-content-strategist 平台规范库接入")
    print("=" * 60)
    results = []
    results.append(await test_analyze_positioning())
    results.append(await test_generate_topic_calendar())
    results.append(await test_predict_trends())
    results.append(await test_analyze_competitor_real())
    print("=" * 60)
    if all(results):
        print("全部通过 [ALL PASS]")
    else:
        print(f"通过 {sum(results)}/{len(results)}")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
