#!/usr/bin/env python3
"""
直接测试诊断流程，不通过 orchestrator
"""

import asyncio
import sys
from pathlib import Path

# 设置路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "packages/knowledge-base/src"))
sys.path.insert(0, str(project_root / "packages/lumina-skills/src"))
sys.path.insert(0, str(project_root / "apps/rpa/src"))

print(f"Python path: {sys.path[:5]}")

async def test():
    print("\n" + "="*60)
    print("直接测试 diagnose_account")
    print("="*60)
    
    try:
        from lumina_skills.diagnosis import diagnose_account
        
        result = await diagnose_account(
            account_url="",  # 空 URL
            platform="douyin",
            user_id="test_user",
            use_crawler=True,
            account_name="余者来来"
        )
        
        print(f"\n结果:")
        print(f"  data_source: {result.get('data_source')}")
        print(f"  health_score: {result.get('health_score')}")
        
        if result.get('data_source') == 'rpa_crawler':
            print("\n✅ 成功使用 RPA 抓取真实数据!")
            print(f"  昵称: {result.get('account_gene', {}).get('nickname')}")
            print(f"  粉丝: {result.get('metrics', {}).get('followers')}")
        else:
            print("\n⚠️ 使用基础分析 (RPA 可能失败)")
            print(f"  原因: {result.get('note')}")
            
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test())
