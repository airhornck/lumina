"""
测试 RPA 抓取平台热门话题 — 结果写入文件避免编码问题
"""

import asyncio
import json
import sys
from pathlib import Path

root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root / "packages" / "lumina-skills" / "src"))
sys.path.insert(0, str(root / "apps" / "rpa" / "src"))


async def test_all_platforms():
    from lumina_skills.tool_skills import fetch_trending_topics

    platforms = [
        ("douyin", "抖音"),
        ("xiaohongshu", "小红书"),
        ("bilibili", "B站"),
    ]

    results = {}
    for platform, name in platforms:
        print(f"测试 {name}...")
        try:
            result = await fetch_trending_topics(
                platform=platform,
                category="general",
                limit=10,
            )
            results[name] = {
                "platform": platform,
                "success": bool(result.get("topics")),
                "count": len(result.get("topics", [])),
                "topics": result.get("topics", []),
                "error": result.get("error"),
                "data_source": result.get("data_source"),
            }
        except Exception as e:
            results[name] = {
                "platform": platform,
                "success": False,
                "error": str(e),
            }

    # 写入文件
    output_file = Path(__file__).resolve().parent / "rpa_test_results.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\n结果已保存到: {output_file}")
    for name, data in results.items():
        status = "OK" if data.get("success") else "FAIL"
        count = data.get("count", 0)
        print(f"  {name}: {status} ({count} 条)")


if __name__ == "__main__":
    asyncio.run(test_all_platforms())
