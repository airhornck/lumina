import pytest

from orchestra.skills.weekly_ops_brief import metrics_engine, trend_analyzer, report_generator, skill


class TestMetricsEngine:
    def test_avg_engagement_rate(self):
        contents = [
            {"metrics": {"views": 1000, "likes": 100, "comments": 20, "collections": 30, "shares": 5}},
            {"metrics": {"views": 1000, "likes": 50, "comments": 10, "collections": 15, "shares": 0}},
        ]
        rate = metrics_engine.avg_engagement_rate(contents)
        assert rate > 0

    def test_viral_rate(self):
        contents = [
            {"metrics": {"views": 1000, "likes": 500, "comments": 100, "collections": 50, "shares": 20}},
            {"metrics": {"views": 1000, "likes": 10, "comments": 0, "collections": 0, "shares": 0}},
        ]
        assert metrics_engine.viral_rate(contents, threshold=0.05) == 0.5

    def test_fan_conversion_efficiency(self):
        stats = {"new_followers": 200, "total_views": 100000}
        assert metrics_engine.fan_conversion_efficiency(stats) == pytest.approx(0.002, rel=1e-3)


class TestTrendAnalyzer:
    def test_identify_content_type_performance(self):
        contents = [
            {"content_type": "图文", "metrics": {"views": 1000, "likes": 100, "comments": 20, "collections": 30, "shares": 5}},
            {"content_type": "图文", "metrics": {"views": 1000, "likes": 100, "comments": 20, "collections": 30, "shares": 5}},
            {"content_type": "视频", "metrics": {"views": 1000, "likes": 10, "comments": 0, "collections": 0, "shares": 0}},
        ]
        perf = trend_analyzer.content_type_performance(contents)
        assert perf["图文"]["avg_engagement_rate"] > perf["视频"]["avg_engagement_rate"]

    def test_top_performers(self):
        contents = [
            {"title": "A", "metrics": {"views": 1000, "likes": 100, "comments": 20, "collections": 30, "shares": 5}},
            {"title": "B", "metrics": {"views": 1000, "likes": 10, "comments": 0, "collections": 0, "shares": 0}},
        ]
        tops = trend_analyzer.top_performers(contents, n=1)
        assert tops[0]["title"] == "A"

    def test_problem_detection(self):
        contents = [
            {"content_type": "测评", "metrics": {"views": 1000, "likes": 10, "comments": 0, "collections": 0, "shares": 0}},
            {"content_type": "教程", "metrics": {"views": 1000, "likes": 100, "comments": 20, "collections": 30, "shares": 5}},
        ]
        problems = trend_analyzer.detect_problems(contents)
        assert any("测评" in p for p in problems)

    def test_strategy_suggestions(self):
        contents = [
            {"content_type": "教程", "metrics": {"views": 1000, "likes": 100, "comments": 20, "collections": 30, "shares": 5}},
            {"content_type": "测评", "metrics": {"views": 1000, "likes": 10, "comments": 0, "collections": 0, "shares": 0}},
        ]
        plans = trend_analyzer.generate_plans(contents)
        assert any("教程" in p for p in plans)
        assert any("测评" in p for p in plans)


class TestReportGenerator:
    def test_render_contains_3p_sections(self):
        data = {
            "contents": [
                {"title": "爆款笔记", "content_type": "图文", "platform": "xiaohongshu", "published_at": "2026-07-01T12:00:00",
                 "metrics": {"views": 10000, "likes": 500, "comments": 50, "collections": 100, "shares": 20}},
            ],
            "stats": {"total_contents": 1, "total_views": 10000, "new_followers": 100},
        }
        report = report_generator.render_3p_report(data)
        assert "PROGRESS" in report
        assert "PROBLEMS" in report
        assert "PLANS" in report

    def test_render_top_performers_table(self):
        data = {
            "contents": [
                {"title": "A", "content_type": "图文", "platform": "xiaohongshu", "published_at": "2026-07-01T12:00:00",
                 "metrics": {"views": 1000, "likes": 100, "comments": 20, "collections": 30, "shares": 5}},
            ],
            "stats": {},
        }
        report = report_generator.render_3p_report(data)
        assert "TOP" in report


class TestWeeklyOpsBriefSkill:
    def test_skill_disabled(self, monkeypatch):
        monkeypatch.setenv("LUMINA_ENABLE_WEEKLY_SNAPSHOT_SKILL", "false")
        result = skill.run_sync("周报", None, {}, [])
        assert "关闭" in result

    def test_skill_returns_report(self, monkeypatch):
        monkeypatch.setenv("LUMINA_ENABLE_WEEKLY_SNAPSHOT_SKILL", "true")
        context = {
            "metrics": {
                "contents": [
                    {"title": "爆款笔记", "content_type": "图文", "platform": "xiaohongshu", "published_at": "2026-07-01T12:00:00",
                     "metrics": {"views": 10000, "likes": 500, "comments": 50, "collections": 100, "shares": 20}},
                ],
                "stats": {"total_contents": 1, "total_views": 10000, "new_followers": 100},
            }
        }
        result = skill.run_sync("帮我生成本周快报", None, context, [])
        assert "PROGRESS" in result
        assert "PROBLEMS" in result
        assert "PLANS" in result
