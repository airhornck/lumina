"""
LLM 调用工具集

为所有 Skill 提供统一的 LLM 调用接口，确保真实调用并处理错误
"""

from __future__ import annotations

import os
import json
from typing import Any, Dict, Optional, List


async def call_llm(
    prompt: str,
    skill_name: str,
    temperature: float = 0.7,
    response_format: Optional[Dict[str, Any]] = None,
    max_tokens: int = 2000,
    fallback_response: Optional[Dict[str, Any]] = None,
    user_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    统一 LLM 调用接口
    
    Args:
        prompt: 提示词
        skill_name: Skill 名称（用于路由到正确的 LLM 配置）
        temperature: 温度
        response_format: 响应格式（如 {"type": "json_object"}）
        max_tokens: 最大 token 数
        fallback_response: 失败时的回退响应
        user_id: 用户唯一标识（用于 token 用量统计）
        
    Returns:
        解析后的 JSON 响应或 fallback
    """
    # 首先尝试使用 llm_hub
    try:
        from llm_hub import get_client
        client = get_client(skill_name=skill_name)
        
        if client and client.config.api_key:
            response = await client.complete(
                prompt=prompt,
                temperature=temperature,
                max_tokens=max_tokens,
                response_format=response_format,
                _usage_meta={"user_id": user_id, "skill_name": skill_name} if user_id else None,
            )
            
            # 尝试解析 JSON
            if response_format and response_format.get("type") == "json_object":
                try:
                    return json.loads(response)
                except json.JSONDecodeError:
                    # 尝试从文本中提取 JSON
                    return _extract_json_from_text(response) or fallback_response or {"error": "JSON解析失败", "raw": response}
            
            return {"content": response, "source": "llm_hub"}
    except Exception as e:
        print(f"[call_llm] llm_hub 调用失败: {e}")
    
    # 尝试直接使用 litellm（从环境变量读取配置）
    try:
        return await _call_litellm_direct(
            prompt=prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format=response_format,
            user_id=user_id,
            skill_name=skill_name,
        )
    except Exception as e:
        print(f"[call_llm] litellm 直接调用失败: {e}")
    
    # 返回 fallback
    if fallback_response:
        return {**fallback_response, "_source": "fallback", "_error": str(e)}
    
    raise RuntimeError(f"LLM 调用失败且未提供 fallback: {e}")


async def _call_litellm_direct(
    prompt: str,
    temperature: float = 0.7,
    max_tokens: int = 2000,
    response_format: Optional[Dict[str, Any]] = None,
    user_id: Optional[str] = None,
    skill_name: Optional[str] = None,
) -> Dict[str, Any]:
    """直接使用 litellm 调用（从环境变量读取配置）"""
    import litellm
    
    # 从环境变量读取配置
    provider = os.getenv("LLM_PROVIDER", "openai")
    model = os.getenv("LLM_MODEL", "gpt-4o-mini")
    api_key = os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY")
    api_base = os.getenv("LLM_API_BASE")
    
    if not api_key:
        raise ValueError("未找到 LLM API Key，请设置 LLM_API_KEY 或 OPENAI_API_KEY 环境变量")
    
    # 构建模型 ID
    model_id = f"{provider}/{model}" if provider != "openai" else model
    
    kwargs = {
        "model": model_id,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
        "max_tokens": max_tokens,
        "api_key": api_key,
    }
    
    if api_base:
        kwargs["api_base"] = api_base
    
    if response_format and provider == "openai":
        kwargs["response_format"] = response_format
    
    resp = await litellm.acompletion(**kwargs)
    content = resp.choices[0].message.content or ""
    
    # 上报 token 用量
    usage = getattr(resp, "usage", None)
    if usage and user_id:
        from llm_hub.usage_reporter import report_usage
        await report_usage(
            user_id=user_id,
            model=model_id,
            prompt_tokens=getattr(usage, "prompt_tokens", 0) or 0,
            completion_tokens=getattr(usage, "completion_tokens", 0) or 0,
            total_tokens=getattr(usage, "total_tokens", 0) or 0,
            skill_name=skill_name,
        )
    
    if response_format and response_format.get("type") == "json_object":
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            return _extract_json_from_text(content) or {"content": content}
    
    return {"content": content.strip()}


def _extract_json_from_text(text: str) -> Optional[Dict[str, Any]]:
    """从文本中提取 JSON"""
    import re
    
    # 尝试找到 JSON 代码块
    patterns = [
        r'```json\s*(.*?)\s*```',  # ```json ... ```
        r'```\s*(.*?)\s*```',       # ``` ... ```
        r'\{.*\}',                  # {...}
    ]
    
    for pattern in patterns:
        matches = re.findall(pattern, text, re.DOTALL)
        for match in matches:
            try:
                return json.loads(match)
            except json.JSONDecodeError:
                continue
    
    return None


async def stream_llm(
    messages: List[Dict[str, str]],
    skill_name: str,
    temperature: float = 0.7,
    max_tokens: int = 2000,
):
    """
    流式 LLM 调用
    
    Args:
        messages: 消息列表
        skill_name: Skill 名称
        temperature: 温度
        max_tokens: 最大 token 数
        
    Yields:
        文本增量
    """
    try:
        from llm_hub import get_client
        client = get_client(skill_name=skill_name)
        
        if client and client.config.api_key:
            async for chunk in client.stream_completion(
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            ):
                yield chunk
            return
    except Exception as e:
        print(f"[stream_llm] llm_hub 失败: {e}")
    
    # 直接调用
    try:
        import litellm
        import os
        
        provider = os.getenv("LLM_PROVIDER", "openai")
        model = os.getenv("LLM_MODEL", "gpt-4o-mini")
        api_key = os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY")
        api_base = os.getenv("LLM_API_BASE")
        
        model_id = f"{provider}/{model}" if provider != "openai" else model
        
        kwargs = {
            "model": model_id,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "api_key": api_key,
            "stream": True,
        }
        
        if api_base:
            kwargs["api_base"] = api_base
        
        stream = await litellm.acompletion(**kwargs)
        async for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            if delta and delta.content:
                yield delta.content
                
    except Exception as e:
        yield f"[Error: {str(e)}]"


def build_prompt(template: str, variables: Dict[str, Any]) -> str:
    """
    构建提示词
    
    Args:
        template: 模板字符串，使用 {variable} 占位
        variables: 变量字典
        
    Returns:
        填充后的提示词
    """
    try:
        return template.format(**variables)
    except KeyError as e:
        missing = str(e).strip("'")
        return template.format(**{**variables, missing: f"[{missing}]"})


# 预定义的提示词模板
PROMPT_TEMPLATES = {
    "positioning_analysis": """作为资深内容策略师，请为以下账号进行定位分析：
    
平台：{platform}
赛道：{niche}
目标受众：{target_audience}
对标账号：{competitor_accounts}

请提供：
1. 一句话定位声明（我是谁，为谁，提供什么价值）
2. 目标人群画像（年龄、性别、痛点、需求）
3. 3-5个内容支柱（核心内容方向）
4. 差异化策略（如何与竞品区隔）
5. 发布频率建议

以 JSON 格式输出：
{{
    "positioning_statement": "...",
    "target_persona": {{"age": "...", "gender": "...", "pain_points": []}},
    "content_pillars": [],
    "differentiation": "...",
    "posting_frequency": "..."
}}""",

    "content_generation": """作为资深文案创作者，请为{platform}平台创作一篇{content_type}：

主题：{topic}
调性：{tone}
关键词：{keywords}
内容DNA：{content_dna}

平台特点：
- 结构：{structure}
- Emoji使用：{emoji_usage}
- 长度：{length}

请生成：
1. 吸睛标题（使用数字、悬念或利益点）
2. 正文内容
3. 相关标签（5-8个）
4. 封面文案（15字以内）
5. 引导行动的结尾

以 JSON 格式输出：
{{
    "title": "...",
    "content": "...",
    "hashtags": [],
    "cover_copy": "...",
    "call_to_action": "..."
}}""",

    "script_generation": """作为资深短视频编剧，请为{platform}平台创作一个{duration}秒的视频脚本：

主题：{topic}
钩子类型：{hook_type}
目标受众：{target_audience}

要求：
1. 前3秒必须有强钩子
2. 每15秒一个信息点或情绪起伏
3. 结尾有明确的CTA
4. 标注画面提示

以 JSON 格式输出：
{{
    "title": "...",
    "hook": "前3秒钩子文案",
    "script_segments": [
        {{"time": "0-3s", "content": "...", "visual": "..."}}
    ],
    "visual_notes": [],
    "bgm_suggestion": "...",
    "total_duration": {duration}
}}""",

    "comment_reply": """基于以下评论生成合适的回复：

评论内容：{comment}
评论者信息：{commenter_info}
内容上下文：{content_context}
期望回复风格：{tone}

要求：
1. 回复要自然、有温度
2. 体现对评论内容的关注和理解
3. 适当引导进一步互动
4. 可附带1-2个合适的emoji

以 JSON 格式输出：
{{
    "reply_text": "...",
    "reply_tone": "...",
    "suggested_emoji": [],
    "follow_up_action": "..."
}}""",

    "competitor_analysis": """分析以下竞品账号：

竞品ID：{competitor_id}
平台：{platform}
分析深度：{analysis_depth}

请提供：
1. 账号概览（粉丝数、互动率、发布频率估计）
2. 内容风格分析
3. 优势识别
4. 可学习的策略
5. Top 3 表现最佳内容分析

以 JSON 格式输出分析结果。""",
}


def get_prompt_template(template_name: str) -> str:
    """获取预定义提示词模板"""
    return PROMPT_TEMPLATES.get(template_name, "")
