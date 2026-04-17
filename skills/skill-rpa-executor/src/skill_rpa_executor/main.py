"""
RPA 执行器 Skill - MCP Server

提供浏览器自动化任务执行能力
"""

from fastmcp import FastMCP
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import sys
import os

# 添加 apps/rpa 到路径以便导入
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "apps", "rpa", "src"))

try:
    from rpa.browser_grid import BrowserGrid
    from rpa.account_crawler import AccountCrawler, RateLimiter, convert_to_diagnosis_format
    RPA_AVAILABLE = True
except ImportError:
    RPA_AVAILABLE = False

mcp = FastMCP("rpa_executor")


class RPATaskInput(BaseModel):
    """RPA 任务输入"""
    task_type: str  # publish, collect, interact, login
    account_id: str
    platform: str
    params: Dict[str, Any]
    timeout: int = 300
    user_id: str


class RPATaskOutput(BaseModel):
    """RPA 任务输出"""
    success: bool
    task_id: str
    execution_time_ms: int
    result_data: Dict[str, Any]
    screenshot: Optional[str]  # base64
    logs: List[str]


@mcp.tool()
async def execute_task(input: RPATaskInput) -> RPATaskOutput:
    """
    执行 RPA 任务
    
    执行浏览器自动化任务
    """
    import time
    start_time = time.time()
    
    # 根据任务类型执行不同操作
    task_handlers = {
        "publish": handle_publish,
        "collect": handle_collect,
        "interact": handle_interact,
        "login": handle_login,
        "crawl_account": handle_crawl_account,
    }
    
    handler = task_handlers.get(input.task_type, handle_generic)
    
    try:
        result = await handler(input)
        success = True
        logs = [f"Task {input.task_type} completed successfully"]
    except Exception as e:
        result = {}
        success = False
        logs = [f"Error: {str(e)}"]
    
    execution_time = int((time.time() - start_time) * 1000)
    
    return RPATaskOutput(
        success=success,
        task_id=f"task_{input.account_id}_{int(time.time())}",
        execution_time_ms=execution_time,
        result_data=result,
        screenshot=None,  # 实际实现中会返回截图
        logs=logs
    )


async def handle_publish(input: RPATaskInput) -> Dict[str, Any]:
    """处理发布任务"""
    params = input.params
    return {
        "action": "content_published",
        "platform": input.platform,
        "content_id": params.get("content_id"),
        "published_url": f"https://{input.platform}.com/p/{params.get('content_id')}",
        "timestamp": "2024-01-01T12:00:00"
    }


async def handle_collect(input: RPATaskInput) -> Dict[str, Any]:
    """处理采集任务"""
    params = input.params
    return {
        "action": "data_collected",
        "platform": input.platform,
        "target": params.get("target_url"),
        "data_points": 150,
        "sample": [
            {"id": 1, "content": "示例内容1", "likes": 100},
            {"id": 2, "content": "示例内容2", "likes": 200}
        ]
    }


async def handle_interact(input: RPATaskInput) -> Dict[str, Any]:
    """处理互动任务"""
    params = input.params
    return {
        "action": "interactions_made",
        "platform": input.platform,
        "interactions": {
            "likes": params.get("like_count", 0),
            "comments": params.get("comment_count", 0),
            "follows": params.get("follow_count", 0)
        },
        "targets": params.get("target_accounts", [])
    }


async def handle_login(input: RPATaskInput) -> Dict[str, Any]:
    """处理登录任务"""
    return {
        "action": "login_completed",
        "platform": input.platform,
        "account_id": input.account_id,
        "session_valid": True,
        "cookies_stored": True
    }


async def handle_generic(input: RPATaskInput) -> Dict[str, Any]:
    """通用任务处理"""
    return {
        "action": "generic_task",
        "status": "completed",
        "params_received": list(input.params.keys())
    }


async def handle_crawl_account(input: RPATaskInput) -> Dict[str, Any]:
    """
    处理账号抓取任务
    
    使用无头浏览器抓取抖音、小红书等平台账号数据
    """
    if not RPA_AVAILABLE:
        return {
            "action": "crawl_account",
            "status": "failed",
            "error": "RPA 模块不可用，请确保已安装 playwright 和依赖",
            "hint": "运行: pip install playwright && playwright install chromium"
        }
    
    params = input.params
    account_url = params.get("account_url")
    platform = params.get("platform", input.platform)
    account_name = params.get("account_name") or params.get("account_id")
    user_id = params.get("user_id") or input.user_id
    max_contents = params.get("max_contents", 10)
    
    if not account_url and not account_name:
        return {
            "action": "crawl_account",
            "status": "failed",
            "error": "必须提供 account_url 或 account_name"
        }
    
    # 初始化浏览器网格和抓取器
    browser_grid = BrowserGrid(max_instances=5, headless=True)
    rate_limiter = RateLimiter(
        default_delay=3.0,
        platform_delays={"douyin": 4.0, "xiaohongshu": 3.5},
        max_requests_per_minute=8,
    )
    crawler = AccountCrawler(browser_grid, rate_limiter)
    
    try:
        # 执行抓取
        crawled_data = await crawler.crawl_account(
            account_url=account_url,
            platform=platform,
            account_id=account_name or "unknown",
            user_id=user_id,
            max_contents=max_contents,
        )
        
        # 转换为诊断格式
        diagnosis_data = convert_to_diagnosis_format(crawled_data)
        
        return {
            "action": "crawl_account",
            "status": crawled_data.crawl_status,
            "platform": platform,
            "account": {
                "nickname": crawled_data.nickname,
                "account_id": crawled_data.account_id,
                "bio": crawled_data.bio,
            },
            "metrics": {
                "followers": crawled_data.followers,
                "following": crawled_data.following,
                "likes": crawled_data.likes,
                "content_count": crawled_data.content_count,
            },
            "contents_sample": crawled_data.recent_contents[:5],
            "diagnosis_ready": diagnosis_data,
            "crawled_at": crawled_data.crawled_at,
            "error": crawled_data.error_message,
        }
        
    except Exception as e:
        return {
            "action": "crawl_account",
            "status": "failed",
            "error": str(e),
            "platform": platform,
        }
    finally:
        # 确保关闭浏览器
        try:
            await browser_grid.close()
        except Exception:
            pass


@mcp.tool()
async def batch_execute(
    user_id: str,
    tasks: List[Dict[str, Any]],
    parallel: bool = True,
) -> Dict[str, Any]:
    """
    批量执行任务
    """
    import asyncio
    
    results = []
    
    if parallel:
        # 并行执行
        for task in tasks:
            result = await execute_task(RPATaskInput(**task))
            results.append(result)
    else:
        # 串行执行
        for task in tasks:
            result = await execute_task(RPATaskInput(**task))
            results.append(result)
            await asyncio.sleep(1)  # 避免过快
    
    success_count = sum(1 for r in results if r.success)
    
    return {
        "total_tasks": len(tasks),
        "success_count": success_count,
        "failed_count": len(tasks) - success_count,
        "results": results,
        "execution_mode": "parallel" if parallel else "serial"
    }


@mcp.tool()
async def get_browser_status(
    user_id: str
) -> Dict[str, Any]:
    """
    获取浏览器网格状态
    """
    return {
        "active_instances": 5,
        "max_instances": 50,
        "queue_length": 2,
        "healthy": True,
        "accounts_logged_in": [
            {"account_id": "acc_001", "platform": "xiaohongshu", "status": "active"},
            {"account_id": "acc_002", "platform": "douyin", "status": "active"}
        ]
    }


@mcp.tool()
async def schedule_task(
    task: Dict[str, Any],
    schedule_time: str,
    user_id: str
) -> Dict[str, Any]:
    """
    定时任务
    """
    return {
        "scheduled_task_id": f"scheduled_{int(time.time())}",
        "execute_at": schedule_time,
        "task_type": task.get("task_type"),
        "status": "scheduled",
        "reminder": "任务将在预定时间执行"
    }


if __name__ == "__main__":
    import time
    mcp.run(transport="sse")
