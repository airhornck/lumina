"""
账号抓取器测试

测试 RPA 账号诊断端到端流程
"""

import pytest
from unittest.mock import Mock


class TestAccountCrawler:
    """测试账号抓取器"""
    
    @pytest.mark.asyncio
    async def test_rate_limiter(self):
        """测试速率限制器"""
        import time
        from rpa.account_crawler import RateLimiter
        
        limiter = RateLimiter(
            default_delay=0.1,
            max_requests_per_minute=100,
        )
        
        start = time.time()
        await limiter.acquire("test")
        await limiter.acquire("test")
        elapsed = time.time() - start
        
        # 应该至少有 0.1 秒延迟
        assert elapsed >= 0.1
    
    @pytest.mark.asyncio
    async def test_parse_number(self):
        """测试数字解析"""
        from rpa.account_crawler import AccountCrawler
        
        crawler = AccountCrawler(Mock())
        
        assert crawler._parse_number("1.2w") == 12000
        assert crawler._parse_number("5万") == 50000
        assert crawler._parse_number("1.5k") == 1500
        assert crawler._parse_number("1234") == 1234
        assert crawler._parse_number("") == 0
        assert crawler._parse_number(None) == 0
    
    @pytest.mark.asyncio
    async def test_convert_to_diagnosis_format(self):
        """测试诊断格式转换"""
        from rpa.account_crawler import (
            CrawledAccountData,
            convert_to_diagnosis_format,
        )
        
        crawled = CrawledAccountData(
            platform="douyin",
            account_id="test_user",
            nickname="测试用户",
            bio="分享干货内容",
            followers=50000,
            following=100,
            likes=100000,
            content_count=50,
            recent_contents=[
                {"title": "教程：如何做内容", "likes": 1000},
                {"title": "日常生活记录", "likes": 500},
            ],
            crawl_status="success",
        )
        
        result = convert_to_diagnosis_format(crawled)
        
        assert "account_gene" in result
        assert "health_score" in result
        assert "key_issues" in result
        assert "raw_metrics" in result
        assert result["platform"] == "douyin"
        assert result["raw_metrics"]["followers"] == 50000
    
    @pytest.mark.asyncio
    async def test_diagnose_account_with_fallback(self):
        """测试诊断账号（带回退）"""
        from lumina_skills.diagnosis import (
            _generate_basic_diagnosis,
        )
        
        # 测试基础诊断生成
        result = _generate_basic_diagnosis(
            account_url="https://www.douyin.com/user/test",
            platform="douyin",
            user_id="test_user",
            spec=Mock(),
        )
        
        assert result["ok"] is True
        assert result["data_source"] == "basic_analysis"
        assert "account_gene" in result
        assert "health_score" in result


class TestRPAIntegration:
    """测试 RPA 集成"""
    
    @pytest.mark.asyncio
    async def test_skill_rpa_executor_crawl_account(self):
        """测试 skill-rpa-executor crawl_account 任务"""
        from skill_rpa_executor.main import handle_crawl_account
        
        # 模拟输入
        mock_input = Mock()
        mock_input.params = {
            "account_url": "https://www.douyin.com/user/test",
            "platform": "douyin",
            "user_id": "test_user",
        }
        mock_input.platform = "douyin"
        mock_input.user_id = "test_user"
        
        # 由于 RPA 需要真实浏览器，这里只测试函数结构
        # 实际抓取测试需要手动运行
        result = await handle_crawl_account(mock_input)
        
        assert "action" in result
        assert result["action"] == "crawl_account"
        # 如果没有安装 playwright，应该返回错误
        assert "status" in result


class TestAntiDetection:
    """测试反检测功能"""
    
    def test_fingerprint_generation(self):
        """测试指纹生成"""
        from rpa.anti_detection import FingerprintGenerator
        
        fp1 = FingerprintGenerator.generate(seed="test1")
        fp2 = FingerprintGenerator.generate(seed="test1")
        fp3 = FingerprintGenerator.generate(seed="test2")
        
        # 相同种子应该生成相同指纹
        assert fp1.user_agent == fp2.user_agent
        assert fp1.screen_resolution == fp2.screen_resolution
        
        # 不同种子应该生成不同指纹
        assert fp1.user_agent != fp3.user_agent or fp1.screen_resolution != fp3.screen_resolution
    
    def test_stealth_scripts(self):
        """测试隐身脚本"""
        from rpa.anti_detection import AntiDetectionLayer
        
        layer = AntiDetectionLayer()
        scripts = layer.get_stealth_scripts()
        
        assert len(scripts) >= 3
        # 检查是否包含关键脚本
        all_scripts = " ".join(scripts)
        assert "webdriver" in all_scripts.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
