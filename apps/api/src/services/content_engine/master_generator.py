from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, Optional

from llm_hub import get_client

logger = logging.getLogger(__name__)


def _extract_json(text: str) -> Optional[Dict[str, Any]]:
    """从文本中提取 JSON 对象，支持 markdown 代码块。

    如果 LLM 返回的是 JSON 字符串（如 '"foo"'）或其他非对象类型，
    统一视为失败并返回 None，避免调用方直接对 str/list 使用 .get()。
    """
    text = text.strip()
    # 尝试直接解析
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass
    # 尝试提取 markdown 代码块
    patterns = [
        r'```json\s*(.*?)\s*```',
        r'```\s*(.*?)\s*```',
        r'\{.*\}',
    ]
    for pattern in patterns:
        matches = re.findall(pattern, text, re.DOTALL)
        for match in matches:
            try:
                parsed = json.loads(match)
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError:
                continue
    return None


class MasterGenerator:
    """母稿生成器：基于用户消息和定位信息生成核心内容母稿。"""

    async def generate(
        self,
        message: str,
        positioning: Dict[str, Any],
        seed_topic: Dict[str, Any] | None = None,
        user_position: Dict[str, Any] | None = None,
        content_type: str = "图文",
    ) -> Dict[str, Any]:
        prompt = self._build_prompt(message, positioning, seed_topic, content_type)

        client = get_client(skill_name="cross_platform_content")
        if not client:
            client = get_client()

        if not client or not client.config.api_key:
            logger.warning("No LLM client available for master generation")
            return {
                "title": message[:50] if message else "未命名",
                "content": message if message else "",
                "hashtags": [],
                "topic": message[:30] if message else "通用",
            }

        try:
            response = await client.complete(
                prompt=prompt,
                response_format={"type": "json_object"},
                temperature=0.7,
                max_tokens=4096,
            )
            logger.debug("MasterGenerator raw response: %r", response)
            if not response or not response.strip():
                logger.warning("Empty LLM response for master generation")
                raise ValueError("Empty response")
            data = _extract_json(response)
            if not data:
                raise ValueError("Could not extract JSON from response")
            return {
                "title": data.get("title", ""),
                "content": data.get("content", ""),
                "hashtags": data.get("hashtags", []),
                "topic": data.get("topic", ""),
                "cover_copy": data.get("cover_copy", ""),
                "call_to_action": data.get("call_to_action", ""),
            }
        except Exception:
            logger.exception("Master content generation failed")
            return {
                "title": message[:50] if message else "未命名",
                "content": message if message else "",
                "hashtags": [],
                "topic": message[:30] if message else "通用",
            }

    def _build_prompt(
        self,
        message: str,
        positioning: Dict[str, Any],
        seed_topic: Dict[str, Any] | None,
        content_type: str,
    ) -> str:
        persona = positioning.get("target_persona", {})
        pillars = positioning.get("content_pillars", [])

        prompt = f"""你是一位资深内容创作者。请基于以下账号定位信息，创作一篇高质量的内容母稿。

【账号定位】
定位声明：{positioning.get('positioning_statement', '未指定')}
目标受众：{persona.get('age', '')} {persona.get('gender', '')}
核心痛点：{', '.join(persona.get('pain_points', []))}
内容需求：{', '.join(persona.get('needs', []))}
内容支柱：{', '.join(pillars)}
差异化策略：{positioning.get('differentiation', '')}

【创作主题】
{message}

【内容类型】
{content_type}
"""

        if seed_topic:
            prompt += f"""
【选题信息】
- 名称：{seed_topic.get('name', '')}
- 切入角度：{', '.join(seed_topic.get('angles', []))}
"""

        prompt += """
【输出要求】
- 标题吸引人但不做标题党，符合账号定位调性
- 正文 300-800 字，信息密度高，符合目标受众阅读习惯
- 标签 5-8 个，精准且有热度
- 输出严格 JSON 格式：
{
  "title": "标题",
  "content": "正文内容",
  "hashtags": ["标签1", "标签2"],
  "topic": "核心主题",
  "cover_copy": "封面文案（可选）",
  "call_to_action": "行动号召（可选）"
}
"""
        return prompt
