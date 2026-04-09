#!/usr/bin/env python3
"""
测试账号诊断完整流程

验证从用户输入到 RPA 抓取的完整流程
"""

import asyncio
import sys
from pathlib import Path

# 添加路径
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "apps" / "rpa" / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent / "packages" / "lumina-skills" / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent / "packages" / "knowledge-base" / "src"))


async def test_diagnose_with_name():
    """测试通过账号名进行诊断"""
    print("\n" + "="*60)
    print("测试: 通过账号名诊断 (抖音 - 余者来来)")
    print("="*60)
    
    try:
        from lumina_skills.diagnosis import diagnose_account
        
        # 模拟从用户输入提取的信息
        result = await diagnose_account(
            account_url="",  # 空URL
            platform="douyin",
            user_id="test_user",
            use_crawler=True,
            account_name="余者来来"  # 通过账号名搜索
        )
        
        print(f"\n诊断结果:")
        print(f"  数据来源: {result.get('data_source')}")
        print(f"  健康分: {result.get('health_score')}")
        
        if result.get('data_source') == 'rpa_crawler':
            print(f"  昵称: {result.get('account_gene', {}).get('nickname')}")
            print(f"  粉丝数: {result.get('metrics', {}).get('followers')}")
            print("✅ 成功使用 RPA 抓取真实数据！")
        else:
            print("⚠️  使用了基础分析（RPA可能失败或未启用）")
            print(f"  备注: {result.get('note')}")
        
        return result.get('data_source') == 'rpa_crawler'
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_extract_account_info():
    """测试账号信息提取"""
    print("\n" + "="*60)
    print("测试: 账号信息提取")
    print("="*60)
    
    test_cases = [
        ("帮我分析个账号，抖音平台，余者来来", "douyin", "余者来来"),
        ("小红书 美妆博主小王", "xiaohongshu", "美妆博主小王"),
        ("抖音：张三", "douyin", "张三"),
        ("我在抖音叫 李四", "douyin", "李四"),
    ]
    
    try:
        # 简单模拟提取逻辑
        import re
        
        for user_input, expected_platform, expected_account in test_cases:
            platform_mapping = {
                "小红书": "xiaohongshu",
                "抖音": "douyin",
            }
            
            # 尝试匹配
            pattern = re.search(
                r"(小红书|抖音).{0,5}[，,、:\s]+([\w\u4e00-\u9fa5]{2,20})",
                user_input
            )
            
            if pattern:
                platform_cn = pattern.group(1)
                account = pattern.group(2).strip()
                platform_en = platform_mapping.get(platform_cn, "unknown")
                
                match = (platform_en == expected_platform and account == expected_account)
                status = "✅" if match else "❌"
                print(f"{status} 输入: {user_input[:30]}...")
                print(f"   提取: {platform_en}/{account}")
                if not match:
                    print(f"   期望: {expected_platform}/{expected_account}")
            else:
                print(f"❌ 未匹配: {user_input[:30]}...")
        
        return True
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        return False


async def main():
    print("\n" + "="*60)
    print("账号诊断流程测试")
    print("="*60)
    
    # 测试1: 账号信息提取
    await test_extract_account_info()
    
    # 测试2: 完整诊断流程
    await test_diagnose_with_name()
    
    print("\n" + "="*60)
    print("测试完成")
    print("="*60)
    print("\n如果测试2显示 '使用了基础分析'，请检查:")
    print("  1. 是否安装了 playwright: pip install playwright")
    print("  2. 是否安装了浏览器: playwright install chromium")
    print("  3. 网络连接是否正常")


if __name__ == "__main__":
    asyncio.run(main())
