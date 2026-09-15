from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, Optional

from knowledge_base.platform_registry import PlatformRegistry
from knowledge_base.methodology_registry import MethodologyRegistry
from llm_hub import get_client

logger = logging.getLogger(__name__)


def _extract_json(text: str) -> Optional[Dict[str, Any]]:
    """从文本中提取 JSON 对象，支持 markdown 代码块。

    如果 LLM 返回的是 JSON 字符串（如 '"foo"'）或其他非对象类型，
    统一视为失败并返回 None，避免调用方直接对 str/list 使用 .get()。
    """
    text = text.strip()
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass
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


class PlatformAdaptor:
    """平台适配器：将母稿适配为特定平台风格的内容。"""

    async def adapt(
        self,
        master_content: Dict[str, Any],
        platform: str,
        positioning: Dict[str, Any],
        content_type: str = "图文",
    ) -> Dict[str, Any]:
        spec = PlatformRegistry().load(platform)
        methodology = MethodologyRegistry().find_best_match(
            query=master_content.get("topic", ""),
            industry=positioning.get("industry", ""),
            goal="",
        )

        prompt = self._build_platform_prompt(
            master_content=master_content,
            platform=platform,
            spec=spec,
            methodology=methodology,
            positioning=positioning,
            content_type=content_type,
        )

        client = get_client(skill_name="cross_platform_content")
        if not client:
            client = get_client()

        if not client or not client.config.api_key:
            logger.warning("No LLM client available for platform adaptation")
            return {
                "title": master_content.get("title", ""),
                "body": master_content.get("content", ""),
                "hashtags": master_content.get("hashtags", []),
                "platform": platform,
            }

        try:
            response = await client.complete(
                prompt=prompt,
                response_format={"type": "json_object"},
                temperature=0.7,
                max_tokens=4096,
            )
            data = _extract_json(response)
            if not data:
                raise ValueError("Could not extract JSON from response")
            return {
                "title": data.get("title", master_content.get("title", "")),
                "body": data.get("body", master_content.get("content", "")),
                "hashtags": data.get("hashtags", master_content.get("hashtags", [])),
                "hook": data.get("hook", ""),
                "best_time": data.get("best_time", ""),
                "platform": platform,
            }
        except Exception:
            logger.exception("Platform adaptation failed for %s", platform)
            return {
                "title": master_content.get("title", ""),
                "body": master_content.get("content", ""),
                "hashtags": master_content.get("hashtags", []),
                "platform": platform,
            }

    def _get_platform_style_guide(self, platform: str) -> str:
        """返回各平台的风格改写要求"""
        guides = {
            "xiaohongshu": """小红书风格要求：
- 语气亲切、像闺蜜分享，多用 emoji 和感叹号
- 正文要有"亲测""实测""安利"等种草感词汇
- 加入个人体验描述和情感共鸣
- 结构可用"痛点引入→解决方案→使用感受→购买建议"
- 标签要带 # 号，精准且有热度""",
            "douyin": """抖音风格要求：
- 短句、快节奏、口语化，适合口播
- 开头必须有强钩子（悬念/冲突/利益点）
- 内容精简，去掉过多细节描述，保留核心信息
- 多用"你知道吗""千万别""直接抄"等互动话术
- 结尾引导点赞关注""",
            "bilibili": """B站风格要求：
- 深度分析感，可适当增加背景知识和原理讲解
- 语气像 UP 主对粉丝说话，真诚、有态度
- 在关键转折点预留弹幕互动点（如"这里你们怎么看"）
- 结构清晰，可用分点或时间轴
- 适当增加梗或行业黑话，增强社区感""",
        }
        return guides.get(platform, "根据平台特点进行适当风格调整")

    def _build_platform_prompt(
        self,
        master_content: Dict[str, Any],
        platform: str,
        spec: Any,
        methodology: Any,
        positioning: Dict[str, Any],
        content_type: str,
    ) -> str:
        # 平台 DNA
        dna_lines: list[str] = []
        if spec and hasattr(spec, "content_dna") and spec.content_dna:
            for item in spec.content_dna:
                element = item.get("element", "") if isinstance(item, dict) else getattr(item, "element", "")
                value = item.get("value", "") if isinstance(item, dict) else getattr(item, "value", "")
                if element:
                    dna_lines.append(f"{element}: {value}")

        # 审核规则
        audit_lines: list[str] = []
        if spec and hasattr(spec, "audit_rules") and spec.audit_rules:
            for rule in spec.audit_rules:
                category = rule.get("category", "") if isinstance(rule, dict) else getattr(rule, "category", "")
                forbidden = rule.get("forbidden_terms", []) if isinstance(rule, dict) else getattr(rule, "forbidden_terms", [])
                if category and forbidden:
                    audit_lines.append(f"{category}类禁用词: {', '.join(forbidden)}")

        # 格式约束
        format_constraints: list[str] = []
        if spec and hasattr(spec, "content_formats") and spec.content_formats:
            cfg = spec.content_formats.get(content_type)
            if cfg and isinstance(cfg, dict) and not cfg.get("note"):
                for k, v in cfg.items():
                    if k == "title":
                        continue
                    if isinstance(v, dict):
                        sub_parts = [f"{sk}={sv}" for sk, sv in v.items() if sk not in ("note",)]
                        format_constraints.append(f"{k}: {', '.join(sub_parts)}")
                    else:
                        format_constraints.append(f"{k}: {v}")

        # 方法论引导
        meth_guide = ""
        if methodology:
            name = getattr(methodology, "name", "") or (methodology.raw.get("name", "") if hasattr(methodology, "raw") else "")
            steps = getattr(methodology, "steps", []) or (methodology.raw.get("steps", []) if hasattr(methodology, "raw") else [])
            if name:
                meth_guide = f"内容方法论：{name}\n"
                if steps:
                    meth_guide += f"步骤框架：{steps}\n"

        # 定位约束
        positioning_info = ""
        if positioning and positioning.get("positioning_statement"):
            positioning_info = f"""【账号定位约束】
定位声明：{positioning.get('positioning_statement', '')}
目标受众：{positioning.get('target_persona', {}).get('age', '')} {positioning.get('target_persona', {}).get('gender', '')}
内容支柱：{', '.join(positioning.get('content_pillars', []))}
适配要求：改写后的内容必须保持上述账号定位一致性，不能偏离账号人设。
"""

        platform_names = {"xiaohongshu": "小红书", "douyin": "抖音", "bilibili": "B站"}
        platform_cn = platform_names.get(platform, platform)

        return f"""请将以下内容改写为适合 **{platform_cn}** 平台的版本。

【内容类型】{content_type}

【平台 DNA】
{chr(10).join(dna_lines) if dna_lines else "（无特定 DNA 约束）"}

【审核规则】
{chr(10).join(audit_lines) if audit_lines else "（无特定审核规则）"}

【格式约束】
{chr(10).join(format_constraints) if format_constraints else "（无特定格式约束）"}

{meth_guide}
{positioning_info}

【原始内容】
标题：{master_content.get('title', '')}
正文：{master_content.get('content', '')}
标签：{', '.join(master_content.get('hashtags', []))}

【平台风格要求】
{self._get_platform_style_guide(platform)}

【输出要求】
请输出严格符合以下 JSON 格式的内容。注意：body 必须根据上方【平台风格要求】进行实质性改写，不能只是复制原文：
{{
  "title": "平台适配后的标题",
  "body": "平台适配后的正文内容（符合平台风格）",
  "hashtags": ["标签1", "标签2", "标签3"],
  "hook": "如果是视频平台，写出黄金3秒钩子；图文平台可留空",
  "best_time": "建议发布时间"
}}
"""
