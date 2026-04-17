"""
验证 skill-bulk-creative 是否正确接入方法论匹配
"""
import asyncio
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT / "packages" / "knowledge-base" / "src"))
sys.path.insert(0, str(PROJECT_ROOT / "packages" / "lumina-skills" / "src"))
sys.path.insert(0, str(PROJECT_ROOT / "skills" / "skill-bulk-creative" / "src"))
sys.path.insert(0, str(PROJECT_ROOT / "apps" / "rpa" / "src"))

from skill_bulk_creative.main import generate_variations, batch_optimize, BulkVariationInput  # noqa: E402
from knowledge_base.methodology_registry import MethodologyRegistry  # noqa: E402


async def test_generate_variations_has_methodology():
    result = await generate_variations(
        BulkVariationInput(
            master_content={"topic": "如何做账号", "title": "做账号指南", "content": "内容...", "hashtags": ["tag1"]},
            target_accounts=[
                {"id": "a1", "type": "细分领域", "niche": "美妆"},
                {"id": "a2", "type": "场景化", "scene": "通勤"},
                {"id": "a3", "type": "地域化", "city": "上海"},
                {"id": "a4", "type": "通用"},
            ],
            user_id="u1",
        )
    )
    available = MethodologyRegistry().list_ids()
    for v in result.variations:
        meth = v.get("recommended_methodology", "")
        assert meth in available, f"变体引用了不存在的方法论: {meth}"
        assert "methodology_guide" in v, "变体中应包含 methodology_guide"
        assert len(v["methodology_guide"]) > 0, "methodology_guide 不应为空"
    print("[PASS] generate_variations 为每个变体推荐了真实存在的方法论")
    return True


async def test_batch_optimize_has_methodology():
    result = await batch_optimize(
        contents=[
            {"id": "c1", "content": "正文1", "hashtags": ["h1"], "platform": "xiaohongshu"},
            {"id": "c2", "content": "正文2", "hashtags": ["h2"], "platform": "douyin"},
        ],
        optimization_goal="conversion",
        user_id="u1",
    )
    available = MethodologyRegistry().list_ids()
    for item in result["results"]:
        meth = item.get("recommended_methodology", "")
        assert meth in available, f"优化结果引用了不存在的方法论: {meth}"
        assert "methodology_guide" in item, "优化结果中应包含 methodology_guide"
    print("[PASS] batch_optimize 按 conversion 目标推荐了方法论")
    return True


async def main():
    print("=" * 60)
    print("验证 skill-bulk-creative 方法论接入")
    print("=" * 60)
    results = []
    results.append(await test_generate_variations_has_methodology())
    results.append(await test_batch_optimize_has_methodology())
    print("=" * 60)
    if all(results):
        print("全部通过 [ALL PASS]")
    else:
        print(f"通过 {sum(results)}/{len(results)}")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
