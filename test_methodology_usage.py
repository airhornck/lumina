"""
检查方法论库（MethodologyRegistry）是否正确运用在策略层及相关 Skill 中
"""
import asyncio
import sys
from pathlib import Path
import inspect

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT / "packages" / "knowledge-base" / "src"))
sys.path.insert(0, str(PROJECT_ROOT / "packages" / "lumina-skills" / "src"))
sys.path.insert(0, str(PROJECT_ROOT / "skills" / "skill-content-strategist" / "src"))
sys.path.insert(0, str(PROJECT_ROOT / "skills" / "skill-creative-studio" / "src"))
sys.path.insert(0, str(PROJECT_ROOT / "apps" / "rpa" / "src"))

from knowledge_base.methodology_registry import MethodologyRegistry  # noqa: E402
from lumina_skills.assets import retrieve_methodology  # noqa: E402
from lumina_skills.content import generate_text, select_topic  # noqa: E402
from lumina_skills.methodology_utils import build_methodology_prompt  # noqa: E402


async def test_retrieve_methodology_uses_registry():
    result = await retrieve_methodology("AIDA", "beauty")
    assert result.get("methodology_id") == "aida_advanced"
    print("[PASS] retrieve_methodology 正确使用了 MethodologyRegistry")
    return True


async def test_generate_text_source_uses_methodology_utils():
    """通过源码确认 generate_text 已接入方法论工具"""
    source = inspect.getsource(generate_text)
    assert "build_methodology_prompt" in source, "generate_text 应调用 build_methodology_prompt"
    assert "match_methodology_for_content" in source, "generate_text 应调用 match_methodology_for_content"

    # 直接验证工具链：pas_framework 的 prompt 构建正常
    meth_prompt = build_methodology_prompt("pas_framework")
    assert "PAS" in meth_prompt or "pas_framework" in meth_prompt.lower()
    assert "痛点" in meth_prompt or "problem" in meth_prompt.lower()
    print("[PASS] generate_text 源码已接入 methodology_utils，且工具链可正确构建 PAS 方法论 prompt")
    return True


async def test_select_topic_uses_real_methodologies():
    result = await select_topic(industry="tech", platform="xiaohongshu", user_id="u1")
    topics = result.get("recommended_topics", [])
    assert len(topics) > 0
    available = MethodologyRegistry().list_ids()
    for t in topics:
        meth = t.get("methodology", "")
        assert meth in available, f"选题引用了不存在的方法论: {meth}"
    print(f"[PASS] select_topic 动态引用了真实存在的方法论: {set(t['methodology'] for t in topics)}")
    return True


async def test_content_strategist_injects_methodology():
    from skill_content_strategist.main import analyze_positioning, PositioningInput
    from lumina_skills import llm_utils

    captured = {}
    original = llm_utils.call_llm

    async def mock(*, prompt, **kwargs):
        captured["prompt"] = prompt
        return kwargs.get("fallback_response", {"content": prompt})

    llm_utils.call_llm = mock
    try:
        await analyze_positioning(
            PositioningInput(platform="xiaohongshu", niche="美妆", user_id="u1")
        )
    finally:
        llm_utils.call_llm = original

    prompt = captured.get("prompt", "")
    assert "定位理论" in prompt or "differentiation" in prompt, (
        "analyze_positioning 应注入 positioning 方法论内容"
    )
    print("[PASS] skill-content-strategist 的 analyze_positioning 已注入定位方法论")
    return True


async def test_creative_studio_injects_methodology():
    from skill_creative_studio.main import generate_text, TextGenerationInput
    from lumina_skills import llm_utils

    captured = {}
    original = llm_utils.call_llm

    async def mock(*, prompt, **kwargs):
        captured["prompt"] = prompt
        return kwargs.get("fallback_response", {"content": prompt})

    llm_utils.call_llm = mock
    try:
        await generate_text(
            TextGenerationInput(topic="如何做账号", platform="xiaohongshu", content_type="post", user_id="u1")
        )
    finally:
        llm_utils.call_llm = original

    prompt = captured.get("prompt", "")
    has_methodology = (
        "方法论框架" in prompt
        or "AIDA" in prompt
        or "PAS" in prompt
        or "StoryArc" in prompt
        or "HookStoryOffer" in prompt
    )
    assert has_methodology, f"creative-studio generate_text 应自动匹配并注入方法论，实际 prompt 开头: {prompt[:200]}"
    print("[PASS] skill-creative-studio 的 generate_text 已自动注入匹配的方法论")
    return True


async def test_orchestra_sop_uses_registry():
    from orchestra.core import MarketingOrchestra
    source = inspect.getsource(MarketingOrchestra)
    has_init = "methodology_lib = MethodologyRegistry()" in source
    has_run_sop = "compile_methodology_dag" in source
    assert has_init and has_run_sop
    print("[PASS] Orchestra 的 SOP 模式正确使用了 MethodologyRegistry")
    return True


async def test_sop_engine_injects_prompt_templates():
    import sop_engine.compiler as compiler

    dag = compiler.compile_methodology_dag("aida_advanced", "xiaohongshu")
    assert len(dag) > 0, "DAG 应有节点"

    first_node = dag[0]
    params = first_node.get("params", {})
    assert "methodology_id" in params, "params 中应有 methodology_id"
    assert "methodology_prompt_templates" in params, "params 中应有 methodology_prompt_templates"

    templates = params["methodology_prompt_templates"]
    assert "attention" in templates, "应注入 attention 模板"
    assert "desire" in templates, "应注入 desire 模板"
    print("[PASS] SOP 引擎已将方法论的 prompt_templates 注入 DAG 节点")
    return True


async def test_topic_calendar_uses_methodology():
    from skill_content_strategist.main import generate_topic_calendar, TopicCalendarInput
    from lumina_skills import llm_utils

    captured = {}
    original = llm_utils.call_llm

    async def mock(*, prompt, **kwargs):
        captured["prompt"] = prompt
        return kwargs.get("fallback_response", {"content": prompt})

    llm_utils.call_llm = mock
    try:
        await generate_topic_calendar(
            TopicCalendarInput(platform="xiaohongshu", niche="美妆", positioning="专业种草", user_id="u1")
        )
    finally:
        llm_utils.call_llm = original

    prompt = captured.get("prompt", "")
    assert "方法论框架" in prompt, "generate_topic_calendar 应注入匹配的方法论框架"
    print("[PASS] skill-content-strategist 的 generate_topic_calendar 已注入内容方法论")
    return True


async def main():
    print("=" * 70)
    print("检查方法论库（MethodologyRegistry）在各层的运用情况")
    print("=" * 70)
    results = []
    results.append(await test_retrieve_methodology_uses_registry())
    results.append(await test_generate_text_source_uses_methodology_utils())
    results.append(await test_select_topic_uses_real_methodologies())
    results.append(await test_content_strategist_injects_methodology())
    results.append(await test_topic_calendar_uses_methodology())
    results.append(await test_creative_studio_injects_methodology())
    results.append(await test_orchestra_sop_uses_registry())
    results.append(await test_sop_engine_injects_prompt_templates())

    print("=" * 70)
    passed = sum(results)
    total = len(results)
    print(f"测试结果: {passed}/{total} 通过")
    if all(results):
        print("所有检查项全部通过！方法论库已在内容生成、选题、策略、创意、SOP 编排各层正确接入。")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
