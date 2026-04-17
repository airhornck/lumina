from __future__ import annotations

import asyncio
import os
import sys
import traceback
from pathlib import Path
from typing import Any, Dict, List, Optional

from knowledge_base.platform_registry import PlatformRegistry


def _ensure_rpa_in_path():
    """确保 RPA 模块在 sys.path 中"""
    possible_paths = [
        Path(__file__).parent.parent.parent.parent.parent / "apps" / "rpa" / "src",
        Path("apps/rpa/src"),
        Path("./apps/rpa/src"),
    ]
    
    for path in possible_paths:
        abs_path = str(path.absolute())
        if abs_path not in sys.path:
            if (path / "rpa" / "browser_grid.py").exists():
                sys.path.insert(0, abs_path)
                return True
    return False


async def diagnose_account(
    account_url: str,
    platform: str,
    user_id: str,
    analysis_depth: str = "standard",
    use_crawler: bool = True,
    rpa_config: Optional[Dict[str, Any]] = None,
    account_name: Optional[str] = None,
    cookies: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    账号基因诊断
    
    优先使用 RPA 抓取真实数据，如果失败则回退到基础分析
    """
    plib = PlatformRegistry()
    spec = plib.load(platform)
    
    print(f"[diagnose_account] 开始诊断: platform={platform}, account_name={account_name}, url={account_url}")
    
    # 尝试使用 RPA 抓取真实数据
    if use_crawler:
        actual_url = account_url
        search_name = account_name
        
        if not actual_url and search_name:
            actual_url = _build_search_url(search_name, platform)
            print(f"[diagnose_account] 构造搜索URL: {actual_url}")
        
        if actual_url or cookies:
            try:
                print(f"[diagnose_account] 开始RPA抓取...")
                crawled_data = await _try_crawl_account(
                    account_url=actual_url,
                    platform=platform,
                    user_id=user_id,
                    rpa_config=rpa_config,
                    account_name=search_name,
                    cookies=cookies,
                )
                
                print(f"[diagnose_account] RPA返回: status={crawled_data.get('status') if crawled_data else 'None'}, nickname={crawled_data.get('nickname') if crawled_data else 'N/A'}")
                
                if crawled_data:
                    status = crawled_data.get("status")
                    
                    # 检查是否获取到了真实数据
                    has_real_data = (
                        crawled_data.get("nickname") or 
                        crawled_data.get("followers", 0) > 0 or
                        crawled_data.get("content_count", 0) > 0
                    )
                    
                    # 需要登录的情况
                    if crawled_data.get("requires_login") or not has_real_data:
                        print(f"[diagnose_account] 需要登录或数据为空，返回提示")
                        return _generate_login_required_diagnosis(
                            platform=platform,
                            user_id=user_id,
                            spec=spec,
                            account_name=account_name,
                            crawled_data=crawled_data,
                        )
                    
                    # 有真实数据，使用抓取的数据
                    if status in ["success", "partial"] and has_real_data:
                        print(f"[diagnose_account] RPA抓取成功，使用真实数据")
                        return _generate_diagnosis_from_crawled(
                            crawled_data=crawled_data,
                            platform=platform,
                            user_id=user_id,
                            spec=spec,
                        )
                    
                    # 其他失败情况
                    print(f"[diagnose_account] RPA未获取到有效数据")
                    return _generate_login_required_diagnosis(
                        platform=platform,
                        user_id=user_id,
                        spec=spec,
                        account_name=account_name,
                        error_msg=crawled_data.get("error"),
                    )
                    
            except Exception as e:
                print(f"[diagnose_account] RPA抓取异常: {e}")
                traceback.print_exc()
                return _generate_login_required_diagnosis(
                    platform=platform,
                    user_id=user_id,
                    spec=spec,
                    account_name=account_name,
                    error_msg=str(e),
                )
        else:
            print(f"[diagnose_account] 没有可用的URL或账号名，跳过RPA")
    
    # 回退到基础诊断
    print(f"[diagnose_account] 使用基础诊断")
    return _generate_basic_diagnosis(
        account_url=account_url,
        platform=platform,
        user_id=user_id,
        spec=spec,
        account_name=account_name,
    )


def _generate_login_required_diagnosis(
    platform: str,
    user_id: str,
    spec: Any,
    account_name: Optional[str] = None,
    crawled_data: Optional[Dict[str, Any]] = None,
    error_msg: Optional[str] = None,
) -> Dict[str, Any]:
    """
    生成需要登录的诊断报告
    
    当无法抓取到真实数据时，提示用户提供登录凭证或主页链接
    """
    account_hint = account_name or "未知账号"
    platform_name = "抖音" if platform == "douyin" else ("小红书" if platform == "xiaohongshu" else platform)
    
    # 尝试从抓取数据中提取有限的信息
    partial_nickname = ""
    if crawled_data:
        partial_nickname = crawled_data.get("nickname", "")
    
    result = {
        "ok": True,
        "data_source": "login_required",
        "note": f"无法获取 {platform_name} 账号的公开数据。{platform_name} 搜索需要登录才能查看完整内容。",
        "account_gene": {
            "content_types": ["lifestyle", "tutorial"],
            "style_tags": ["亲和", "干货"],
            "audience_sketch": "18-35 岁女性为主",
            "account_hint": account_hint,
            "partial_nickname": partial_nickname,
        },
        "health_score": 50.0,  # 未知状态下给中等分数
        "key_issues": [
            f"{platform_name} 需要登录才能获取账号数据",
            "无法访问实时内容进行分析",
        ],
        "improvement_suggestions": [
            {
                "area": "login", 
                "tip": f"请说「登录{platform_name}」获取二维码扫码登录，授权后我可以获取您的真实账号数据",
                "priority": "high"
            },
            {
                "area": "alternative", 
                "tip": f"或直接提供 {platform_name} 主页链接（如 https://www.douyin.com/user/xxx）",
                "priority": "medium"
            },
            {
                "area": "manual", 
                "tip": "也可以手动提供账号数据（粉丝数、作品数、互动率等）进行分析",
                "priority": "low"
            },
        ],
        "recommended_methodology": "aida_advanced",
        "user_id": user_id,
        "platform": platform,
        "login_required": True,
        "suggestions": [
            f"1. 说「登录{platform_name}」扫码授权",
            "2. 或直接提供账号主页链接",
            "3. 或手动提供账号数据",
        ],
    }
    
    if error_msg:
        result["error_detail"] = error_msg
    
    return result


def _build_search_url(account_name: str, platform: str) -> str:
    """从账号名构造搜索 URL"""
    import urllib.parse
    
    encoded_name = urllib.parse.quote(account_name)
    
    if platform == "douyin":
        return f"https://www.douyin.com/search/{encoded_name}?type=user"
    elif platform == "xiaohongshu":
        return f"https://www.xiaohongshu.com/search_result?keyword={encoded_name}&type=user"
    else:
        return f"https://www.douyin.com/search/{encoded_name}?type=user"


async def _try_crawl_account(
    account_url: str,
    platform: str,
    user_id: str,
    rpa_config: Optional[Dict[str, Any]] = None,
    timeout: int = 60,
    account_name: Optional[str] = None,
    cookies: Optional[List[Dict[str, Any]]] = None,
) -> Optional[Dict[str, Any]]:
    """尝试通过 RPA 抓取账号数据"""
    
    _ensure_rpa_in_path()
    
    try:
        from rpa.browser_grid import BrowserGrid
        from rpa.account_crawler import AccountCrawler, RateLimiter, convert_to_diagnosis_format
        
        browser_grid = BrowserGrid(max_instances=3, headless=True)
        rate_limiter = RateLimiter(
            default_delay=3.0,
            platform_delays={"douyin": 4.0, "xiaohongshu": 3.5},
            max_requests_per_minute=8,
        )
        crawler = AccountCrawler(browser_grid, rate_limiter)
        
        crawled_data = await asyncio.wait_for(
            crawler.crawl_account(
                account_url=account_url,
                platform=platform,
                account_id=account_name or user_id,
                user_id=user_id,
                max_contents=10,
                cookies=cookies,
            ),
            timeout=timeout,
        )
        
        return {
            "status": crawled_data.crawl_status,
            "platform": crawled_data.platform,
            "nickname": crawled_data.nickname,
            "bio": crawled_data.bio,
            "followers": crawled_data.followers,
            "following": crawled_data.following,
            "likes": crawled_data.likes,
            "content_count": crawled_data.content_count,
            "recent_contents": crawled_data.recent_contents,
            "diagnosis_ready": convert_to_diagnosis_format(crawled_data),
            "error": crawled_data.error_message,
            "requires_login": crawled_data.requires_login,
        }
        
    except ImportError as e:
        return {"status": "failed", "error": f"RPA模块导入失败: {e}"}
    except Exception as e:
        return {"status": "failed", "error": str(e)}


def _generate_diagnosis_from_crawled(
    crawled_data: Dict[str, Any],
    platform: str,
    user_id: str,
    spec: Any,
) -> Dict[str, Any]:
    """基于抓取数据生成诊断报告"""
    
    diagnosis_ready = crawled_data.get("diagnosis_ready", {})
    
    result = {
        "ok": True,
        "data_source": "rpa_crawler",
        "crawl_status": crawled_data.get("status"),
        "account_gene": diagnosis_ready.get("account_gene", {
            "content_types": ["general"],
            "style_tags": ["真实"],
            "audience_sketch": "18-35 岁用户",
        }),
        "health_score": diagnosis_ready.get("health_score", 60.0),
        "key_issues": diagnosis_ready.get("key_issues", []),
        "improvement_suggestions": diagnosis_ready.get("improvement_suggestions", []),
        "recommended_methodology": "aida_advanced",
        "user_id": user_id,
        "platform": platform,
    }
    
    raw_metrics = diagnosis_ready.get("raw_metrics", {})
    if raw_metrics:
        result["metrics"] = raw_metrics
    
    recent_contents = crawled_data.get("recent_contents", [])
    if recent_contents:
        result["content_samples"] = recent_contents[:5]
    
    return result


def _generate_basic_diagnosis(
    account_url: str,
    platform: str,
    user_id: str,
    spec: Any,
    account_name: Optional[str] = None,
) -> Dict[str, Any]:
    """生成基础诊断报告（无真实数据时）"""
    
    account_hint = account_name or "未知账号"
    
    return {
        "ok": True,
        "data_source": "basic_analysis",
        "note": "无法获取实时数据，以下为基础诊断建议",
        "account_gene": {
            "content_types": ["lifestyle", "tutorial"],
            "style_tags": ["亲和", "干货"],
            "audience_sketch": "18-35 岁女性为主",
            "account_hint": account_hint,
        },
        "health_score": 65.0,
        "key_issues": [
            "无法获取实时数据，建议手动补充账号信息",
        ],
        "improvement_suggestions": [
            {"area": "data_collection", "tip": "建议提供 Cookie 或直接提供账号主页链接"},
        ],
        "recommended_methodology": "aida_advanced",
        "user_id": user_id,
        "platform": platform,
    }


async def analyze_traffic(
    metrics: Dict[str, Any],
    user_id: str,
    platform: str,
    time_range: str = "7d",
) -> Dict[str, Any]:
    views = int(metrics.get("views") or metrics.get("impressions") or 0)
    likes = int(metrics.get("likes") or 0)
    shares = int(metrics.get("shares") or 0)
    ctr = (likes / views * 100) if views else 0.0
    return {
        "funnel_analysis": {
            "exposure": views,
            "engagement_rate": round(ctr, 2),
            "shares": shares,
        },
        "drop_off_points": ["互动率低于行业均值"] if ctr < 3 else [],
        "trend": "stable",
        "anomaly_detection": [],
        "actionable_insights": [f"当前样本曝光 {views}，优先优化封面与标题。"],
    }


# 通用极限词与风险词库（作为平台规则的兜底）
_UNIVERSAL_RISK_TERMS = [
    ("全网最低", "extreme_pricing"),
    ("最低价", "extreme_pricing"),
    ("最便宜", "extreme_pricing"),
    ("最好", "superlative"),
    ("第一", "superlative"),
    ("极致", "superlative"),
    ("顶级", "superlative"),
    ("首选", "superlative"),
    ("绝对", "absolute_claim"),
    ("保证", "absolute_claim"),
    ("百分百", "absolute_claim"),
    ("永不", "absolute_claim"),
    ("疗效", "medical"),
    ("治愈", "medical"),
    ("治疗", "medical"),
]


async def detect_risk(
    content_text: str,
    platform: str,
    content_type: str = "post",
) -> Dict[str, Any]:
    spec = PlatformRegistry().load(platform)
    risks: List[Dict[str, Any]] = []
    flagged: List[Dict[str, Any]] = []
    text = content_text or ""
    # 平台规则
    for rule in spec.audit_rules:
        terms = rule.get("forbidden_terms") or []
        cat = rule.get("category") or "general"
        for t in terms:
            if t and t in text:
                risks.append({"category": cat, "term": t})
                flagged.append({"term": t, "category": cat})
    # 通用兜底词库
    for term, cat in _UNIVERSAL_RISK_TERMS:
        if term in text and not any(f["term"] == term for f in flagged):
            risks.append({"category": cat, "term": term})
            flagged.append({"term": term, "category": cat})
    level = "low"
    if len(flagged) >= 3:
        level = "high"
    elif flagged:
        level = "medium"
    suggestions = []
    if flagged:
        suggestions.append("删除或改写敏感词")
        # 针对极限词给出替代表述建议
        if any(f["category"] in ("extreme_pricing", "superlative", "absolute_claim") for f in flagged):
            suggestions.append("避免使用绝对化用语，可改用'很受欢迎'、'性价比高'等相对表述")
    else:
        suggestions.append("未发现明显违规词")
    return {
        "risk_level": level,
        "risk_categories": list({r["category"] for r in risks}) or ["none"],
        "flagged_terms": flagged,
        "suggestions": suggestions,
        "alternative_phrases": {},
    }
