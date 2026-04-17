"""
测试：生产多平台内容时，是否会根据平台规范库（data/platforms/*.yml）来进行生产
"""
import asyncio
import sys
from pathlib import Path

# 设置项目路径
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT / "packages" / "lumina-skills" / "src"))
sys.path.insert(0, str(PROJECT_ROOT / "packages" / "knowledge-base" / "src"))
sys.path.insert(0, str(PROJECT_ROOT / "packages" / "llm-hub" / "src"))
sys.path.insert(0, str(PROJECT_ROOT / "skills" / "skill-creative-studio" / "src"))
sys.path.insert(0, str(PROJECT_ROOT / "skills" / "skill-content-strategist" / "src"))
sys.path.insert(0, str(PROJECT_ROOT / "skills" / "skill-bulk-creative" / "src"))
sys.path.insert(0, str(PROJECT_ROOT / "apps" / "rpa" / "src"))


async def test_lumina_skills_uses_platform_registry():
    """测试 packages/lumina-skills 的 generate_text 是否读取了平台规范库"""
    from lumina_skills.content import generate_text

    result = await generate_text(
        topic="测试话题",
        platform="xiaohongshu",
        content_dna={},
        user_id="test_user",
    )

    assert "platform_optimization" in result, "结果中应包含 platform_optimization"
    tips = result["platform_optimization"]["tips"]
    tips_str = str(tips)

    # 平台规范库 xiaohongshu_v2024.yml 中包含 hook_position 和 title_length
    assert "hook_position" in tips_str or "0-3s" in tips_str or "title_length" in tips_str, (
        f"未在返回结果中找到平台规范库内容。实际 tips: {tips}"
    )
    print("[PASS] Test 1: packages/lumina-skills 的 generate_text 确实使用了平台规范库")
    return True


async def test_creative_studio_prompt():
    """测试 skill-creative-studio 的 generate_text 是否使用了平台规范库"""
    from skill_creative_studio.main import generate_text, TextGenerationInput
    from lumina_skills import llm_utils

    captured = {}
    original_call_llm = llm_utils.call_llm

    async def mock_call_llm(*, prompt, **kwargs):
        captured["prompt"] = prompt
        return {
            "title": "测试标题",
            "content": "测试内容",
            "hashtags": ["测试"],
            "cover_copy": "测试封面",
            "call_to_action": "测试CTA",
        }

    llm_utils.call_llm = mock_call_llm
    try:
        await generate_text(
            TextGenerationInput(
                topic="测试话题",
                platform="xiaohongshu",
                content_type="post",
                user_id="test_user",
            )
        )
    finally:
        llm_utils.call_llm = original_call_llm

    prompt = captured.get("prompt", "")
    assert prompt, "应捕获到 prompt"

    # 现在 skill-creative-studio 应该读取了 PlatformRegistry
    uses_platform_registry = (
        "hook_position" in prompt
        or "title_length" in prompt
        or "audit_rules" in prompt
        or "禁用词" in prompt
    )

    if uses_platform_registry:
        print("[PASS] Test 2: skill-creative-studio 的 generate_text 使用了平台规范库")
        return True
    else:
        print("[FAIL] Test 2: skill-creative-studio 的 generate_text 未使用平台规范库")
        print("   说明：prompt 中未包含 data/platforms/xiaohongshu_v2024.yml 中定义的规范内容。")
        return False


async def test_content_strategist_prompt():
    """测试 skill-content-strategist 的工具是否使用了平台规范库"""
    from skill_content_strategist.main import analyze_positioning, PositioningInput
    from lumina_skills import llm_utils

    captured = {}
    original_call_llm = llm_utils.call_llm

    async def mock_call_llm(*, prompt, **kwargs):
        captured["prompt"] = prompt
        return {
            "positioning_statement": "P",
            "target_persona": {},
            "content_pillars": [],
            "differentiation": "D",
            "posting_frequency": "每周3更",
        }

    llm_utils.call_llm = mock_call_llm
    try:
        await analyze_positioning(
            PositioningInput(
                platform="xiaohongshu",
                niche="美妆",
                user_id="test_user",
            )
        )
    finally:
        llm_utils.call_llm = original_call_llm

    prompt = captured.get("prompt", "")
    assert prompt, "应捕获到 prompt"

    uses_platform_registry = (
        "hook_position" in prompt
        or "title_length" in prompt
        or "content_dna" in prompt
        or "audit_rules" in prompt
    )

    if uses_platform_registry:
        print("[PASS] Test 3: skill-content-strategist 使用了平台规范库")
        return True
    else:
        print("[FAIL] Test 3: skill-content-strategist 的 analyze_positioning 未使用平台规范库")
        print("   说明：prompt 中没有任何来自 data/platforms/*.yml 的规范内容。")
        return False


async def test_bulk_creative_adapt_platform():
    """测试 skill-bulk-creative 的 adapt_platform 是否使用了平台规范库"""
    from skill_bulk_creative.main import adapt_platform

    result = await adapt_platform(
        content={"content": "这是一个测试内容" * 50, "hashtags": ["tag1", "tag2", "tag3", "tag4", "tag5", "tag6", "tag7", "tag8", "tag9", "tag10"]},
        source_platform="douyin",
        target_platforms=["xiaohongshu", "bilibili"],
        user_id="test_user",
    )

    adaptations = result.get("adaptations", {})
    assert "xiaohongshu" in adaptations, "结果中应包含 xiaohongshu 的适配"

    xhs_style = adaptations["xiaohongshu"].get("style_guide", "")
    # 应包含平台规范库中的 DNA 或审核规则内容
    uses_platform_registry = (
        "hook_position" in xhs_style
        or "title_length" in xhs_style
        or "禁用词" in xhs_style
    )

    if uses_platform_registry:
        print("[PASS] Test 4: skill-bulk-creative 的 adapt_platform 使用了平台规范库")
        return True
    else:
        print("[FAIL] Test 4: skill-bulk-creative 的 adapt_platform 未使用平台规范库")
        print(f"   实际 style_guide: {xhs_style}")
        return False


async def main():
    print("=" * 60)
    print("开始测试：多平台内容生产是否基于平台规范库")
    print("=" * 60)

    results = []
    results.append(await test_lumina_skills_uses_platform_registry())
    results.append(await test_creative_studio_prompt())
    results.append(await test_content_strategist_prompt())
    results.append(await test_bulk_creative_adapt_platform())

    print("=" * 60)
    if all(results):
        print("所有测试通过 [ALL PASS]")
    else:
        passed = sum(results)
        total = len(results)
        print(f"测试结果: {passed}/{total} 通过")
        print("注意：部分内容生产路径未接入平台规范库，建议统一规范来源。")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
