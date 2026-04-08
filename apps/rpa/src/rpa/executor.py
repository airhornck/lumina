"""
RPA 执行器

执行自动化任务
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Callable
from enum import Enum
from datetime import datetime


class TaskStatus(Enum):
    """任务状态"""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class TaskResult:
    """任务执行结果"""
    success: bool
    data: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    screenshot: Optional[str] = None  # Base64 编码
    logs: List[str] = field(default_factory=list)
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    
    @property
    def duration_ms(self) -> int:
        """获取执行耗时（毫秒）"""
        if self.start_time and self.end_time:
            return int((self.end_time - self.start_time).total_seconds() * 1000)
        return 0


@dataclass
class RPATask:
    """RPA 任务定义"""
    id: str
    name: str
    platform: str
    actions: List[Dict[str, Any]]
    account_id: str
    timeout: int = 300  # 秒
    retry_count: int = 3
    metadata: Dict[str, Any] = field(default_factory=dict)


class RPAExecutor:
    """
    RPA 任务执行器
    
    执行浏览器自动化任务
    """
    
    def __init__(self, browser_grid):
        """
        初始化
        
        Args:
            browser_grid: BrowserGrid 实例
        """
        self.browser_grid = browser_grid
        self._action_handlers: Dict[str, Callable] = {
            "navigate": self._handle_navigate,
            "click": self._handle_click,
            "type": self._handle_type,
            "upload": self._handle_upload,
            "scroll": self._handle_scroll,
            "wait": self._handle_wait,
            "screenshot": self._handle_screenshot,
            "extract": self._handle_extract,
        }
    
    async def execute(self, task: RPATask) -> TaskResult:
        """
        执行任务
        
        Args:
            task: RPA 任务
        
        Returns:
            执行结果
        """
        result = TaskResult(success=False)
        result.start_time = datetime.now()
        
        # 获取或创建会话
        session = await self.browser_grid.create_session(
            task.account_id,
            task.platform
        )
        
        try:
            for action in task.actions:
                action_type = action.get("type")
                handler = self._action_handlers.get(action_type)
                
                if not handler:
                    raise ValueError(f"Unknown action type: {action_type}")
                
                # 执行动作
                action_result = await handler(session.page, action)
                result.logs.append(f"Executed {action_type}: {action_result}")
                
                # 如果动作失败，尝试重试
                if not action_result.get("success"):
                    for attempt in range(task.retry_count):
                        result.logs.append(f"Retry {attempt + 1}/{task.retry_count}")
                        action_result = await handler(session.page, action)
                        if action_result.get("success"):
                            break
                    else:
                        raise RuntimeError(f"Action failed after {task.retry_count} retries: {action_type}")
            
            result.success = True
            result.data = {"message": "Task completed successfully"}
            
        except Exception as e:
            result.success = False
            result.error = str(e)
            result.logs.append(f"Error: {str(e)}")
            
            # 失败时截图
            try:
                screenshot = await session.page.screenshot()
                result.screenshot = screenshot
            except Exception:
                pass
        
        finally:
            result.end_time = datetime.now()
        
        return result
    
    async def execute_batch(self, tasks: List[RPATask]) -> List[TaskResult]:
        """
        批量执行任务
        
        Args:
            tasks: 任务列表
        
        Returns:
            结果列表
        """
        import asyncio
        
        results = await asyncio.gather(
            *[self.execute(task) for task in tasks],
            return_exceptions=True
        )
        
        # 处理异常
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                processed_results.append(TaskResult(
                    success=False,
                    error=str(result)
                ))
            else:
                processed_results.append(result)
        
        return processed_results
    
    # Action Handlers
    
    async def _handle_navigate(self, page, action: Dict) -> Dict[str, Any]:
        """处理导航动作"""
        url = action.get("url")
        await page.goto(url, wait_until="networkidle")
        return {"success": True, "url": url}
    
    async def _handle_click(self, page, action: Dict) -> Dict[str, Any]:
        """处理点击动作"""
        selector = action.get("selector")
        await page.click(selector)
        return {"success": True, "selector": selector}
    
    async def _handle_type(self, page, action: Dict) -> Dict[str, Any]:
        """处理输入动作"""
        selector = action.get("selector")
        text = action.get("text")
        
        await page.fill(selector, "")
        await page.type(selector, text, delay=random.randint(50, 150))
        
        return {"success": True, "selector": selector, "text_length": len(text)}
    
    async def _handle_upload(self, page, action: Dict) -> Dict[str, Any]:
        """处理文件上传"""
        selector = action.get("selector")
        file_path = action.get("file_path")
        
        input_element = await page.query_selector(selector)
        await input_element.set_input_files(file_path)
        
        return {"success": True, "file": file_path}
    
    async def _handle_scroll(self, page, action: Dict) -> Dict[str, Any]:
        """处理滚动动作"""
        direction = action.get("direction", "down")
        amount = action.get("amount", 500)
        
        if direction == "down":
            await page.evaluate(f"window.scrollBy(0, {amount})")
        else:
            await page.evaluate(f"window.scrollBy(0, -{amount})")
        
        return {"success": True, "direction": direction, "amount": amount}
    
    async def _handle_wait(self, page, action: Dict) -> Dict[str, Any]:
        """处理等待动作"""
        import asyncio
        
        wait_type = action.get("wait_type", "time")
        
        if wait_type == "time":
            seconds = action.get("seconds", 1)
            await asyncio.sleep(seconds)
        elif wait_type == "selector":
            selector = action.get("selector")
            await page.wait_for_selector(selector)
        elif wait_type == "navigation":
            await page.wait_for_load_state("networkidle")
        
        return {"success": True, "wait_type": wait_type}
    
    async def _handle_screenshot(self, page, action: Dict) -> Dict[str, Any]:
        """处理截图动作"""
        selector = action.get("selector")
        
        if selector:
            element = await page.query_selector(selector)
            screenshot = await element.screenshot()
        else:
            screenshot = await page.screenshot()
        
        return {"success": True, "screenshot": screenshot}
    
    async def _handle_extract(self, page, action: Dict) -> Dict[str, Any]:
        """处理数据提取动作"""
        selector = action.get("selector")
        attribute = action.get("attribute", "text")
        
        elements = await page.query_selector_all(selector)
        data = []
        
        for element in elements:
            if attribute == "text":
                text = await element.inner_text()
                data.append(text)
            else:
                value = await element.get_attribute(attribute)
                data.append(value)
        
        return {"success": True, "data": data, "count": len(data)}


import random  # 用于输入延迟
