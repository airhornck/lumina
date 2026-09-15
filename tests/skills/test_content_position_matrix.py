"""Phase 3 P2 TDD Harness：ContentPositionMatrix 评分与可视化 Red 状态测试。"""

from __future__ import annotations

import pytest


def test_professional_score_high_for_tutorial():
    from orchestra.skills.content_position_matrix import scoring_engine

    text = """【保姆级教程】早C晚A正确入门步骤

第一步：建立耐受，从低浓度开始
第二步：晨间用VC精华，记得防晒
第三步：晚间用VA醇，隔天使用
实测数据：连续4周后，毛孔细腻度提升32%。
"""
    score = scoring_engine.score_professional(text)
    assert score >= 6.0


def test_entertainment_score_high_for_dramatic_content():
    from orchestra.skills.content_position_matrix import scoring_engine

    text = """没想到！我用早C晚A一个月后竟然变成这样？
评论区都在问：这是不是开了美颜？
真实对比图放最后了，记得看到最后！
"""
    score = scoring_engine.score_entertainment(text)
    assert score >= 6.0


def test_engagement_intensity_prediction():
    from orchestra.skills.content_position_matrix import scoring_engine

    intensity = scoring_engine.predict_engagement_intensity(professional=7.0, entertainment=8.0)
    assert 0.0 <= intensity <= 1.0
    assert intensity >= 0.05


def test_quadrant_classification():
    from orchestra.skills.content_position_matrix import matrix_plotter

    assert matrix_plotter.classify_quadrant(7, 8) == "viral爆款区"
    assert matrix_plotter.classify_quadrant(7, 4) == "知识干货区"
    assert matrix_plotter.classify_quadrant(3, 8) == "娱乐消遣区"
    assert matrix_plotter.classify_quadrant(3, 3) == "日常分享区"


def test_ascii_matrix_contains_marker():
    from orchestra.skills.content_position_matrix import matrix_plotter

    chart = matrix_plotter.render_ascii_matrix(professional=7, entertainment=8)
    assert "★" in chart
    assert "viral爆款区" in chart or "爆款区" in chart


@pytest.mark.asyncio
async def test_content_position_matrix_skill_output():
    from orchestra.skills.content_position_matrix import skill

    result = await skill.run(
        message="分析一下这个内容的定位：没想到！我用早C晚A一个月后竟然变成这样？实测对比数据在最后。",
        platform="xiaohongshu",
        context={},
        history=[],
    )

    assert isinstance(result, str)
    assert "★" in result
    assert "专业度" in result
    assert "娱乐度" in result
    assert "差异化" in result or "定位" in result
