from __future__ import annotations

from typing import Any, Dict, List


class HtmlRenderer:
    """增强版 HTML 渲染器
    - 支持多平台差异化（小红书/抖音/B站/公众号等）
    - 支持视频脚本时间轴
    - 支持平台规则元信息卡片（从 platform spec 动态读取）
    - 字段名兼容（body / content）
    """

    def render(
        self,
        content: Dict[str, Any],
        positioning: Dict[str, Any],
        platform: str | None = None,
        is_master: bool = False,
        spec: Any = None,
        content_type: str = "图文",
    ) -> str:
        title = content.get("title", "未命名")
        body = content.get("body") or content.get("content", "")
        hashtags = content.get("hashtags", [])
        best_time = content.get("best_time", "")
        compliance = content.get("compliance_warnings", [])
        cover_copy = content.get("cover_copy", "")
        call_to_action = content.get("call_to_action", "")

        positioning_block = self._render_positioning(positioning)
        compliance_block = self._render_compliance(compliance)
        platform_specs_block = (
            self._render_platform_specs(spec, content_type, platform)
            if not is_master else ""
        )

        extra_blocks = ""
        if cover_copy:
            extra_blocks += f'<div class="cover-copy"><h4>📱 封面文案</h4><p>{cover_copy}</p></div>'
        if call_to_action:
            extra_blocks += f'<div class="cta"><h4>👉 行动号召</h4><p>{call_to_action}</p></div>'

        platform_fields_block = (
            self._render_platform_fields(content, platform, spec, content_type)
            if not is_master else ""
        )

        platform_name = self._get_platform_display_name(platform) if platform else "母稿"
        version_label = "母稿" if is_master else f"{platform_name} 版本"

        return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title} - {version_label}</title>
    <style>
        body {{
            max-width: 720px;
            margin: 40px auto;
            padding: 0 20px;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            line-height: 1.8;
            color: #333;
            background: #fafafa;
        }}
        .container {{
            background: #fff;
            padding: 32px;
            border-radius: 12px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.06);
        }}
        h1 {{ font-size: 26px; margin-bottom: 12px; color: #1a1a1a; }}
        .tags {{ margin: 16px 0; }}
        .tag {{
            display: inline-block;
            background: #f0f0f0;
            padding: 4px 14px;
            border-radius: 16px;
            font-size: 14px;
            margin-right: 8px;
            margin-bottom: 6px;
            color: #555;
        }}
        .positioning {{
            background: #f0f7ff;
            padding: 16px 20px;
            border-radius: 10px;
            margin: 20px 0;
            border-left: 4px solid #4a90d9;
        }}
        .positioning h3 {{ margin-top: 0; color: #2c5aa0; font-size: 16px; }}
        article {{ font-size: 16px; margin-top: 24px; color: #444; }}
        .compliance {{
            color: #2e7d32;
            font-size: 14px;
            margin-top: 24px;
            padding: 14px 16px;
            border-radius: 8px;
            background: #e8f5e9;
            border-left: 4px solid #4caf50;
        }}
        .compliance.warning {{
            color: #bf360c;
            background: #fff3e0;
            border-left-color: #ff9800;
        }}
        .compliance.warning mark {{
            background: #ffcc80;
            padding: 2px 6px;
            border-radius: 4px;
        }}
        .cover-copy, .cta {{
            background: #f3e5f5;
            padding: 14px 18px;
            border-radius: 10px;
            margin: 18px 0;
            border-left: 4px solid #9c27b0;
        }}
        .cover-copy h4, .cta h4 {{ margin-top: 0; color: #6a1b9a; font-size: 15px; }}

        /* 平台规范卡片 */
        .platform-specs {{
            background: #fff8e1;
            padding: 20px;
            border-radius: 10px;
            margin: 24px 0;
            border-left: 4px solid #ffc107;
        }}
        .platform-specs h3 {{ margin-top: 0; color: #f57c00; font-size: 16px; }}
        .spec-section {{ margin: 14px 0; }}
        .spec-section h4 {{
            font-size: 14px;
            color: #e65100;
            margin-bottom: 8px;
            font-weight: 600;
        }}
        .spec-section ul {{
            margin: 0;
            padding-left: 20px;
            font-size: 14px;
            color: #555;
        }}
        .spec-section li {{ margin: 4px 0; }}
        .spec-table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 14px;
            margin-top: 8px;
        }}
        .spec-table th, .spec-table td {{
            text-align: left;
            padding: 8px 12px;
            border-bottom: 1px solid #e0e0e0;
        }}
        .spec-table th {{
            background: #fff3cd;
            color: #856404;
            font-weight: 600;
            width: 30%;
        }}
        .spec-table td {{ color: #555; }}
        .audit-warning {{
            background: #ffebee;
            border-left-color: #ef5350;
        }}
        .audit-warning h4 {{ color: #c62828; }}

        /* 平台字段区 */
        .platform-fields {{
            background: #e3f2fd;
            padding: 18px 20px;
            border-radius: 10px;
            margin: 20px 0;
            border-left: 4px solid #2196f3;
        }}
        .platform-fields h4 {{
            margin-top: 0;
            color: #1565c0;
            font-size: 15px;
        }}
        .field-row {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 8px 0;
            border-bottom: 1px dashed #bbdefb;
            font-size: 14px;
        }}
        .field-row:last-child {{ border-bottom: none; }}
        .field-label {{ color: #424242; font-weight: 500; }}
        .field-value {{ color: #1565c0; font-weight: 600; }}
        .field-warn {{ color: #e53935; font-weight: 600; }}

        footer {{
            margin-top: 40px;
            padding-top: 20px;
            border-top: 1px solid #eee;
            font-size: 12px;
            color: #999;
            text-align: center;
        }}
        .best-time {{
            background: #e8eaf6;
            padding: 10px 16px;
            border-radius: 8px;
            margin: 16px 0;
            font-size: 14px;
            color: #3949ab;
            border-left: 4px solid #5c6bc0;
        }}
    </style>
</head>
<body>
    <div class="container">
        {positioning_block}
        {platform_specs_block}
        <h1>{title}</h1>
        <div class="tags">
            {''.join(f'<span class="tag">#{t}</span>' for t in hashtags)}
        </div>
        <article>{body.replace(chr(10), '<br>')}</article>
        {extra_blocks}
        {platform_fields_block}
        {'<div class="best-time">🕐 建议发布时间：' + best_time + '</div>' if best_time else ''}
        {compliance_block}
        <footer>
            由 Lumina 智能营销助手生成 · {version_label}
        </footer>
    </div>
</body>
</html>"""

    def _render_platform_specs(self, spec: Any, content_type: str, platform: str | None) -> str:
        if not spec or not platform:
            return ""

        # content_dna
        dna_block = ""
        dna_items: List[str] = []
        if hasattr(spec, "content_dna") and spec.content_dna:
            for item in spec.content_dna:
                if isinstance(item, dict):
                    element = item.get("element", "")
                    value = item.get("value", "")
                else:
                    element = getattr(item, "element", "")
                    value = getattr(item, "value", "")
                if element and value:
                    dna_items.append(f"<li><strong>{element}</strong>：{value}</li>")
        if dna_items:
            dna_block = (
                f'<div class="spec-section">'
                f'<h4>🧬 平台内容 DNA</h4>'
                f'<ul>{"".join(dna_items)}</ul>'
                f'</div>'
            )

        # content_formats
        format_block = ""
        formats = (
            getattr(spec, "content_formats", {})
            if hasattr(spec, "content_formats")
            else {}
        )
        cfg = formats.get(content_type) if formats else None
        if cfg and isinstance(cfg, dict) and not cfg.get("note"):
            rows: List[str] = []
            for field, rules in cfg.items():
                if isinstance(rules, dict):
                    parts: List[str] = []
                    for k, v in rules.items():
                        if k == "note":
                            continue
                        label = self._format_field_label(k)
                        parts.append(f"{label}: {v}")
                    rows.append(f"<tr><td>{field}</td><td>{' | '.join(parts)}</td></tr>")
                else:
                    rows.append(f"<tr><td>{field}</td><td>{rules}</td></tr>")
            if rows:
                format_block = (
                    f'<div class="spec-section">'
                    f'<h4>📐 格式约束（{content_type}）</h4>'
                    f'<table class="spec-table">'
                    f'<tr><th>字段</th><th>约束</th></tr>'
                    f'{"".join(rows)}'
                    f'</table>'
                    f'</div>'
                )

        # audit_rules
        audit_block = ""
        audit_items: List[str] = []
        if hasattr(spec, "audit_rules") and spec.audit_rules:
            for rule in spec.audit_rules:
                if isinstance(rule, dict):
                    category = rule.get("category", "")
                    forbidden = rule.get("forbidden_terms", [])
                    examples = rule.get("examples", [])
                    notes = rule.get("notes", [])
                else:
                    category = getattr(rule, "category", "")
                    forbidden = getattr(rule, "forbidden_terms", [])
                    examples = getattr(rule, "examples", [])
                    notes = getattr(rule, "notes", [])
                if category and forbidden:
                    parts: List[str] = [
                        f"<strong>{category}</strong>类禁用词：{', '.join(forbidden)}"
                    ]
                    if examples:
                        parts.append(f"示例：{', '.join(examples)}")
                    if notes:
                        notes_str = (
                            '; '.join(notes) if isinstance(notes, list) else str(notes)
                        )
                        parts.append(f"注意：{notes_str}")
                    audit_items.append(f"<li>{' | '.join(parts)}</li>")
        if audit_items:
            audit_block = (
                f'<div class="spec-section audit-warning">'
                f'<h4>⚠️ 审核规则</h4>'
                f'<ul>{"".join(audit_items)}</ul>'
                f'</div>'
            )

        if not (dna_block or format_block or audit_block):
            return ""

        platform_display = self._get_platform_display_name(platform)
        return (
            f'<div class="platform-specs">'
            f'<h3>📋 {platform_display} 平台发布规范</h3>'
            f'{dna_block}'
            f'{format_block}'
            f'{audit_block}'
            f'</div>'
        )

    def _render_platform_fields(
        self,
        content: Dict[str, Any],
        platform: str | None,
        spec: Any,
        content_type: str,
    ) -> str:
        if not platform:
            return ""

        fields: List[str] = []

        title = content.get("title", "")
        body = content.get("body") or content.get("content", "")
        hashtags = content.get("hashtags", [])
        hook = content.get("hook", "")

        formats = (
            getattr(spec, "content_formats", {})
            if hasattr(spec, "content_formats")
            else {}
        )
        cfg = formats.get(content_type) if formats else None

        # 标题长度检查
        title_cfg = cfg.get("title", {}) if cfg else {}
        title_max = title_cfg.get("max_chars")
        title_min = title_cfg.get("min_chars")
        title_len = len(title)
        title_status = f"{title_len}字"
        if title_max and title_len > title_max:
            title_status += f' <span class="field-warn">⚠️ 超限制({title_max})</span>'
        elif title_min is not None and title_len < title_min:
            title_status += f' <span class="field-warn">⚠️ 不足({title_min})</span>'
        fields.append(
            f'<div class="field-row">'
            f'<span class="field-label">标题</span>'
            f'<span class="field-value">{title_status}</span>'
            f'</div>'
        )

        # 正文长度检查
        content_cfg = cfg.get("content", {}) if cfg else {}
        content_max = content_cfg.get("max_chars")
        content_min = content_cfg.get("min_chars")
        body_len = len(body)
        body_status = f"{body_len}字"
        if content_max and body_len > content_max:
            body_status += f' <span class="field-warn">⚠️ 超限制({content_max})</span>'
        elif content_min is not None and body_len < content_min:
            body_status += f' <span class="field-warn">⚠️ 不足({content_min})</span>'
        fields.append(
            f'<div class="field-row">'
            f'<span class="field-label">正文</span>'
            f'<span class="field-value">{body_status}</span>'
            f'</div>'
        )

        # 标签数检查
        tags_cfg = cfg.get("tags", {}) if cfg else {}
        tags_max = tags_cfg.get("max_count")
        tags_count = len(hashtags)
        tags_status = f"{tags_count}个"
        if tags_max and tags_count > tags_max:
            tags_status += f' <span class="field-warn">⚠️ 超限制({tags_max})</span>'
        fields.append(
            f'<div class="field-row">'
            f'<span class="field-label">标签</span>'
            f'<span class="field-value">{tags_status}</span>'
            f'</div>'
        )

        # 平台特定字段
        if platform == "xiaohongshu":
            if content_type in ("图文",):
                pic_cfg = cfg.get("pic_num", {}) if cfg else {}
                pic_default = pic_cfg.get("default", "6-9")
                fields.append(
                    f'<div class="field-row">'
                    f'<span class="field-label">建议图片数</span>'
                    f'<span class="field-value">{pic_default}张</span>'
                    f'</div>'
                )
                pic_res = cfg.get("pic_resolution", {}) if cfg else {}
                pic_ratio = pic_res.get("ratio", "3:4至2:1")
                fields.append(
                    f'<div class="field-row">'
                    f'<span class="field-label">图片比例</span>'
                    f'<span class="field-value">{pic_ratio}</span>'
                    f'</div>'
                )
                pic_min = pic_res.get("min", "720*960")
                fields.append(
                    f'<div class="field-row">'
                    f'<span class="field-label">图片分辨率</span>'
                    f'<span class="field-value">{pic_min}起</span>'
                    f'</div>'
                )
            elif content_type in ("视频",):
                vid_cfg = cfg.get("video_duration", {}) if cfg else {}
                vid_default = vid_cfg.get("default", "30秒-1分钟")
                fields.append(
                    f'<div class="field-row">'
                    f'<span class="field-label">建议时长</span>'
                    f'<span class="field-value">{vid_default}</span>'
                    f'</div>'
                )
        elif platform == "douyin":
            duration_tip = content.get("duration_tip", "15-60秒")
            fields.append(
                f'<div class="field-row">'
                f'<span class="field-label">建议时长</span>'
                f'<span class="field-value">{duration_tip}</span>'
                f'</div>'
            )
            vid_res = cfg.get("video_resolution", {}) if cfg else {}
            ratio = vid_res.get("ratio", "9:16竖屏")
            fields.append(
                f'<div class="field-row">'
                f'<span class="field-label">视频比例</span>'
                f'<span class="field-value">{ratio}</span>'
                f'</div>'
            )
            if hook:
                fields.append(
                    f'<div class="field-row">'
                    f'<span class="field-label">黄金钩子</span>'
                    f'<span class="field-value">{hook}</span>'
                    f'</div>'
                )
        elif platform == "bilibili":
            if content_type in ("视频",):
                vid_cfg = cfg.get("video_duration", {}) if cfg else {}
                vid_default = vid_cfg.get("default", "1-10分钟")
                fields.append(
                    f'<div class="field-row">'
                    f'<span class="field-label">建议时长</span>'
                    f'<span class="field-value">{vid_default}</span>'
                    f'</div>'
                )
            if hook:
                fields.append(
                    f'<div class="field-row">'
                    f'<span class="field-label">开篇钩子</span>'
                    f'<span class="field-value">{hook}</span>'
                    f'</div>'
                )
        elif platform == "wechat_official":
            summary = content.get("summary", "")
            if summary:
                fields.append(
                    f'<div class="field-row">'
                    f'<span class="field-label">摘要</span>'
                    f'<span class="field-value">{len(summary)}字</span>'
                    f'</div>'
                )
            cover_cfg = cfg.get("cover", {}) if cfg else {}
            if cover_cfg:
                large = cover_cfg.get("large", {})
                if large:
                    fields.append(
                        f'<div class="field-row">'
                        f'<span class="field-label">封面大图</span>'
                        f'<span class="field-value">{large.get("recommended", "")} ({large.get("ratio", "")})</span>'
                        f'</div>'
                    )

        if not fields:
            return ""

        return (
            f'<div class="platform-fields">'
            f'<h4>📊 内容字段校验</h4>'
            f'{"".join(fields)}'
            f'</div>'
        )

    def _render_positioning(self, positioning: Dict[str, Any]) -> str:
        if not positioning or not positioning.get("positioning_statement"):
            return ""

        persona = positioning.get("target_persona", {})
        pillars = positioning.get("content_pillars", [])
        pillars_html = f"<p>📌 内容支柱：{', '.join(pillars)}</p>" if pillars else ""

        return (
            f'<div class="positioning">'
            f'<h3>🎯 账号定位</h3>'
            f'<p><strong>{positioning.get("positioning_statement", "")}</strong></p>'
            f'<p>👥 目标受众：{persona.get("age", "")} {persona.get("gender", "")}</p>'
            f'{pillars_html}'
            f'</div>'
        )

    def _render_compliance(self, warnings: List[str]) -> str:
        if not warnings:
            return '<div class="compliance">✅ 合规检查通过，未发现违规词</div>'

        items = "<br>".join(f"• {w}" for w in warnings)
        return f'<div class="compliance warning">⚠️ 合规提醒：<br>{items}</div>'

    def _get_platform_display_name(self, platform: str | None) -> str:
        names = {
            "xiaohongshu": "小红书",
            "douyin": "抖音",
            "bilibili": "B站",
            "wechat_official": "微信公众号",
        }
        return names.get(platform, platform or "未知平台")

    def _format_field_label(self, key: str) -> str:
        mapping = {
            "max_chars": "最多字符",
            "min_chars": "最少字符",
            "default": "推荐",
            "max_count": "最多数量",
            "min": "最小值",
            "max": "最大值",
            "recommended": "推荐",
            "supported": "支持格式",
            "ratio": "比例",
            "note": "说明",
            "max_size_mb": "最大体积(MB)",
            "gif_max_size_mb": "GIF最大体积(MB)",
            "recommended_width": "推荐宽度",
            "recommended_ratios": "推荐比例",
            "recommended_format": "推荐格式",
            "max_duration": "最大时长",
            "auto_extract_chars": "自动提取字数",
            "original_min_chars": "原创最低字数",
            "frequency": "发布频率",
            "max_articles_per_push": "每次最多文章数",
            "max_rounds": "最大修改次数",
            "title_max_change": "标题最多修改",
            "body_max_change": "正文最多修改",
            "images_max_replace": "图片最多替换",
            "videos_max_replace": "视频最多替换",
            "cover_editable": "封面可修改",
            "options": "选项",
            "description": "说明",
            "range": "范围",
            "usage": "用途",
            "recommendation": "建议",
        }
        return mapping.get(key, key)
