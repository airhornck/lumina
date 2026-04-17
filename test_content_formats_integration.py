"""
深度验证：content_formats 约束是否被 skill-creative-studio 和 skill-bulk-creative 正确读取
"""
import asyncio
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT / "packages" / "knowledge-base" / "src"))
sys.path.insert(0, str(PROJECT_ROOT / "packages" / "lumina-skills" / "src"))
sys.path.insert(0, str(PROJECT_ROOT / "skills" / "skill-creative-studio" / "src"))
sys.path.insert(0, str(PROJECT_ROOT / "skills" / "skill-bulk-creative" / "src"))

from knowledge_base.platform_registry import PlatformRegistry  # noqa: E402
from skill_creative_studio.main import generate_text, optimize_title, TextGenerationInput  # noqa: E402
from skill_bulk_creative.main import adapt_platform  # noqa: E402
from lumina_skills import llm_utils  # noqa: E402


async def test_creative_studio_title_limit():
    """验证 generate_text 的 prompt 中包含从 content_formats 读取的 title.max_chars"""
    captured = {}
    original = llm_utils.call_llm

    async def mock(*, prompt, **kwargs):
        captured["prompt"] = prompt
        return {"title": "T", "content": "C", "hashtags": [], "cover_copy": "CC", "call_to_action": "CTA"}

    llm_utils.call_llm = mock
    try:
        await generate_text(TextGenerationInput(topic="测试", platform="xiaohongshu", content_type="post", user_id="u1"))
    finally:
        llm_utils.call_llm = original

    prompt = captured["prompt"]
    spec = PlatformRegistry().load("xiaohongshu")
    title_max = spec.content_formats.get("图文", {}).get("title", {}).get("max_chars", 20)
    content_max = spec.content_formats.get("图文", {}).get("content", {}).get("max_chars", 1000)
    tags_max = spec.content_formats.get("图文", {}).get("tags", {}).get("max_count", 10)

    assert f"标题不超过{title_max}字" in prompt, f"prompt 中未出现标题限制 {title_max}，实际: {prompt}"
    assert f"正文内容不超过{content_max}字" in prompt, f"prompt 中未出现正文限制 {content_max}"
    assert f"标签不超过{tags_max}个" in prompt, f"prompt 中未出现标签限制 {tags_max}"
    print(f"[PASS] creative-studio generate_text 正确读取了 content_formats: title_max={title_max}, content_max={content_max}, tags_max={tags_max}")
    return True


async def test_optimize_title_uses_content_formats():
    """验证 optimize_title 的长度检查来自 content_formats 而非硬编码"""
    # bilibili 的仅文字 title.max_chars=40
    long_bili_title = "测试标题长度限制" + "啊" * 35  # 总计 43 字 > 40
    result = await optimize_title([long_bili_title], platform="bilibili", user_id="u1")
    opt = result["optimizations"][0]
    assert "标题过长" in opt["issues"], f"bilibili 标题{len(long_bili_title)}字应提示过长，实际 issues={opt['issues']}"

    # xiaohongshu 图文的 title.max_chars=20
    long_xhs_title = "测试标题" + "啊" * 17  # 总计 21 字 > 20
    result2 = await optimize_title([long_xhs_title], platform="xiaohongshu", user_id="u1")
    opt2 = result2["optimizations"][0]
    assert "标题过长" in opt2["issues"], f"xiaohongshu 标题{len(long_xhs_title)}字应提示过长，实际 issues={opt2['issues']}"

    print("[PASS] optimize_title 的长度检查已基于 content_formats")
    return True


async def test_bulk_creative_length_and_tags():
    """验证 adapt_platform 的内容截断和标签限制来自 content_formats"""
    long_content = "内容" * 600  # 1200字
    many_tags = [f"tag{i}" for i in range(15)]

    result = await adapt_platform(
        content={"content": long_content, "hashtags": many_tags},
        source_platform="xiaohongshu",
        target_platforms=["xiaohongshu", "bilibili", "douyin"],
        user_id="u1",
    )

    spec_xhs = PlatformRegistry().load("xiaohongshu")
    xhs_max = spec_xhs.content_formats.get("图文", {}).get("content", {}).get("max_chars", 1000)
    xhs_tags = spec_xhs.content_formats.get("图文", {}).get("tags", {}).get("max_count", 10)

    spec_bili = PlatformRegistry().load("bilibili")
    # bilibili 仅文字 content.max_chars=40000
    bili_max = spec_bili.content_formats.get("仅文字", {}).get("content", {}).get("max_chars", 40000)

    spec_dy = PlatformRegistry().load("douyin")
    dy_max = spec_dy.content_formats.get("短视频", {}).get("content", {}).get("max_chars", 1000)
    dy_tags = spec_dy.content_formats.get("短视频", {}).get("tags", {}).get("max_count", 10)

    xhs = result["adaptations"]["xiaohongshu"]
    bili = result["adaptations"]["bilibili"]
    dy = result["adaptations"]["douyin"]

    assert len(xhs["content"]) <= xhs_max, f"小红书内容应截断至{xhs_max}字，实际{len(xhs['content'])}"
    assert len(xhs["hashtags"]) <= xhs_tags, f"小红书标签应限制至{xhs_tags}个，实际{len(xhs['hashtags'])}"
    assert len(bili["content"]) <= bili_max, f"B站内容应截断至{bili_max}字，实际{len(bili['content'])}"
    assert len(dy["content"]) <= dy_max, f"抖音内容应截断至{dy_max}字，实际{len(dy['content'])}"
    assert len(dy["hashtags"]) <= dy_tags, f"抖音标签应限制至{dy_tags}个，实际{len(dy['hashtags'])}"

    print(f"[PASS] bulk-creative adapt_platform 正确截断: xhs={xhs_max}/{xhs_tags}, bili={bili_max}, dy={dy_max}/{dy_tags}")
    return True


async def main():
    print("=" * 60)
    print("深度验证 content_formats 集成")
    print("=" * 60)
    results = []
    results.append(await test_creative_studio_title_limit())
    results.append(await test_optimize_title_uses_content_formats())
    results.append(await test_bulk_creative_length_and_tags())
    print("=" * 60)
    if all(results):
        print("全部通过 [ALL PASS]")
    else:
        print(f"通过 {sum(results)}/{len(results)}")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
