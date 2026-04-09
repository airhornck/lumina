#!/usr/bin/env python3
"""
Skill 真实实现测试脚本

测试所有已改造的 Skill 是否能正常工作
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "apps" / "rpa" / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent / "packages" / "llm-hub" / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent / "packages" / "lumina-skills" / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent / "skills" / "skill-content-strategist" / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent / "skills" / "skill-creative-studio" / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent / "skills" / "skill-account-keeper" / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent / "skills" / "skill-data-analyst" / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent / "skills" / "skill-knowledge-miner" / "src"))


async def test_llm_utils():
    """测试 LLM 工具"""
    print("\n" + "="*60)
    print("测试 1: LLM 工具")
    print("="*60)
    
    try:
        from lumina_skills.llm_utils import call_llm
        
        result = await call_llm(
            prompt="请回复'LLM测试成功'",
            skill_name="test",
            fallback_response={"content": "Fallback 响应"}
        )
        
        print(f"✅ LLM 调用成功")
        print(f"   响应: {result.get('content', result)[:100]}...")
        return True
        
    except Exception as e:
        print(f"❌ LLM 调用失败: {e}")
        print("   请检查 LLM_API_KEY 环境变量")
        return False


async def test_rpa_helper():
    """测试 RPA 工具"""
    print("\n" + "="*60)
    print("测试 2: RPA 工具")
    print("="*60)
    
    try:
        from rpa.skill_utils import get_rpa_helper
        
        rpa = get_rpa_helper()
        print(f"✅ RPA Helper 初始化成功")
        
        # 测试获取趋势（不实际抓取，只检查初始化）
        # result = await rpa.fetch_platform_data(
        #     platform="douyin",
        #     data_type="hot_topics",
        #     account_id="test",
        # )
        # print(f"✅ RPA 数据获取成功: {result.success}")
        
        return True
        
    except Exception as e:
        print(f"❌ RPA 初始化失败: {e}")
        print("   请确保已安装 playwright")
        return False


async def test_content_strategist():
    """测试内容策略师 Skill"""
    print("\n" + "="*60)
    print("测试 3: Content Strategist")
    print("="*60)
    
    try:
        from skill_content_strategist.main import analyze_positioning, PositioningInput
        
        result = await analyze_positioning(PositioningInput(
            platform="douyin",
            niche="美妆",
            target_audience="18-25岁女性",
            user_id="test"
        ))
        
        print(f"✅ 定位分析成功")
        print(f"   定位: {result.positioning_statement[:50]}...")
        print(f"   内容支柱: {result.content_pillars}")
        return True
        
    except Exception as e:
        print(f"❌ 定位分析失败: {e}")
        return False


async def test_creative_studio():
    """测试创意工厂 Skill"""
    print("\n" + "="*60)
    print("测试 4: Creative Studio")
    print("="*60)
    
    try:
        from skill_creative_studio.main import generate_text, TextGenerationInput
        
        result = await generate_text(TextGenerationInput(
            topic="如何提高工作效率",
            platform="xiaohongshu",
            content_type="post",
            tone="friendly",
            user_id="test"
        ))
        
        print(f"✅ 文案生成成功")
        print(f"   标题: {result.title}")
        print(f"   内容长度: {len(result.content)} 字符")
        return True
        
    except Exception as e:
        print(f"❌ 文案生成失败: {e}")
        return False


async def test_data_analyst():
    """测试数据分析师 Skill"""
    print("\n" + "="*60)
    print("测试 5: Data Analyst")
    print("="*60)
    
    try:
        from skill_data_analyst.main import diagnose_account, AccountDiagnosisInput
        
        # 使用用户提供的 metrics（不触发 RPA）
        result = await diagnose_account(AccountDiagnosisInput(
            account_url="",  # 空 URL 跳过 RPA
            platform="douyin",
            metrics={
                "followers": 5000,
                "likes": 10000,
                "content_count": 20,
            },
            user_id="test"
        ))
        
        print(f"✅ 账号诊断成功")
        print(f"   健康分: {result.overall_score}")
        print(f"   状态: {result.health_status}")
        return True
        
    except Exception as e:
        print(f"❌ 账号诊断失败: {e}")
        return False


async def test_knowledge_miner():
    """测试知识提取器 Skill"""
    print("\n" + "="*60)
    print("测试 6: Knowledge Miner")
    print("="*60)
    
    try:
        from skill_knowledge_miner.main import analyze_success_content, ContentAnalysisInput
        
        result = await analyze_success_content(ContentAnalysisInput(
            content_data={
                "id": "test_001",
                "title": "3个技巧让你效率翻倍",
                "content": "今天分享3个超实用的效率技巧...",
                "views": 10000,
                "likes": 500,
            },
            platform="douyin",
            user_id="test"
        ))
        
        print(f"✅ 内容分析成功")
        print(f"   成功因素: {len(result.success_factors)} 个")
        print(f"   可复制性: {result.replicability_score}")
        return True
        
    except Exception as e:
        print(f"❌ 内容分析失败: {e}")
        return False


async def test_tool_skills():
    """测试工具 Skills"""
    print("\n" + "="*60)
    print("测试 7: Tool Skills")
    print("="*60)
    
    try:
        from lumina_skills.tool_skills import fetch_industry_news
        
        result = await fetch_industry_news(category="科技", days=3)
        
        print(f"✅ 新闻获取成功")
        print(f"   数据源: {result.get('data_source')}")
        print(f"   新闻数: {len(result.get('news_list', []))}")
        return True
        
    except Exception as e:
        print(f"❌ 新闻获取失败: {e}")
        return False


async def main():
    """运行所有测试"""
    print("\n" + "="*60)
    print("🚀 Skill 真实实现测试")
    print("="*60)
    
    tests = [
        ("LLM 工具", test_llm_utils),
        ("RPA 工具", test_rpa_helper),
        ("Content Strategist", test_content_strategist),
        ("Creative Studio", test_creative_studio),
        ("Data Analyst", test_data_analyst),
        ("Knowledge Miner", test_knowledge_miner),
        ("Tool Skills", test_tool_skills),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            success = await test_func()
            results.append((name, success))
        except Exception as e:
            print(f"❌ {name} 测试异常: {e}")
            results.append((name, False))
    
    # 汇总
    print("\n" + "="*60)
    print("📊 测试结果汇总")
    print("="*60)
    
    passed = sum(1 for _, success in results if success)
    total = len(results)
    
    for name, success in results:
        status = "✅ 通过" if success else "❌ 失败"
        print(f"{status}: {name}")
    
    print(f"\n总计: {passed}/{total} 通过")
    
    if passed < total:
        print("\n⚠️  部分测试失败，请检查:")
        print("   1. 环境变量 LLM_API_KEY 是否设置")
        print("   2. playwright 是否安装")
        print("   3. 网络连接是否正常")
    else:
        print("\n🎉 所有测试通过！")


if __name__ == "__main__":
    asyncio.run(main())
