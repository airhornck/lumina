"""
验证 skill-compliance-officer 是否正确接入平台规范库的审核规则
"""
import asyncio
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT / "packages" / "knowledge-base" / "src"))
sys.path.insert(0, str(PROJECT_ROOT / "skills" / "skill-compliance-officer" / "src"))
sys.path.insert(0, str(PROJECT_ROOT / "apps" / "rpa" / "src"))

from skill_compliance_officer.main import check_content_risk, check_account_health, RiskCheckInput  # noqa: E402


async def test_check_content_risk_uses_platform_registry():
    """验证 check_content_risk 读取了 xiaohongshu_v2024.yml 中的 audit_rules"""
    # xiaohongshu_v2024.yml 中有 medical: ["疗效", "治疗", "治愈"] 和 comparison: ["最好", "第一", "极致"]
    result = await check_content_risk(
        RiskCheckInput(
            content_text="这个产品有最好的疗效，能治愈一切",
            platform="xiaohongshu",
            user_id="u1",
        )
    )

    violations = result.violations
    sources = {v.get("source") for v in violations}
    rules = {v.get("rule") for v in violations}

    assert "platform_registry" in sources, f"应有来自 platform_registry 的违规记录，实际 sources={sources}"
    assert "疗效" in rules or "治愈" in rules or "最好" in rules, f"应命中平台规范库中的禁用词，实际 rules={rules}"
    assert any(v.get("type") == "platform_audit_rule" for v in violations), "应有 platform_audit_rule 类型"

    # 检查建议中是否标注了平台规范库来源
    assert any("平台规范库" in s for s in result.suggestions), "建议中应提示来自平台规范库"
    print("[PASS] check_content_risk 已正确接入平台规范库审核规则")
    return True


async def test_check_content_risk_fallback_builtin():
    """验证不存在的平台会回退到 builtin 规则"""
    result = await check_content_risk(
        RiskCheckInput(
            content_text="这个赌博平台稳赚不赔",
            platform="nonexistent_platform",
            user_id="u1",
        )
    )
    violations = result.violations
    sources = {v.get("source") for v in violations}
    assert "builtin" in sources, f"不存在的平台应回退到 builtin 规则，实际 sources={sources}"
    print("[PASS] 不存在的平台正确回退到 builtin 敏感词库")
    return True


async def test_check_account_health_includes_audit_categories():
    """验证 check_account_health 返回了平台规范库的审核类别"""
    result = await check_account_health(
        account_data={"violations_history": [], "shadow_banned": False},
        platform="xiaohongshu",
        user_id="u1",
    )
    categories = result.get("platform_audit_categories", [])
    assert "medical" in categories, f"xiaohongshu 的 medical 审核类别应被读取，实际 categories={categories}"
    assert "comparison" in categories, f"xiaohongshu 的 comparison 审核类别应被读取，实际 categories={categories}"
    assert any("medical" in r or "comparison" in r for r in result.get("recommendations", [])), (
        "推荐中应包含平台审核类别的提示"
    )
    print("[PASS] check_account_health 已引用平台规范库审核类别")
    return True


async def main():
    print("=" * 60)
    print("验证 skill-compliance-officer 平台规范库接入")
    print("=" * 60)
    results = []
    results.append(await test_check_content_risk_uses_platform_registry())
    results.append(await test_check_content_risk_fallback_builtin())
    results.append(await test_check_account_health_includes_audit_categories())
    print("=" * 60)
    if all(results):
        print("全部通过 [ALL PASS]")
    else:
        print(f"通过 {sum(results)}/{len(results)}")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
