from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Dict, List

from knowledge_base.platform_registry import PlatformRegistry
from services.content_engine.compliance_scanner import ComplianceScanner
from services.content_engine.export_service import ExportRecordService
from services.content_engine.html_renderer import HtmlRenderer
from services.content_engine.master_generator import MasterGenerator
from services.content_engine.platform_adaptor import PlatformAdaptor
from services.content_engine.resource_uploader import ResourceUploader
from services.content_engine.storage import FileSystemStorage
from services.content_engine.summarizer import ContentSummarizer
from services.content_engine.user_profile_service import UserProfileService

logger = logging.getLogger(__name__)


@dataclass
class PlatformChunk:
    type: str           # "master" | "platform"
    platform: str | None
    content: Dict[str, Any]
    warnings: List[str] | None = None


@dataclass
class ContentPipelineResult:
    master_content: Dict[str, Any]
    platform_versions: List[Dict[str, Any]]
    positioning: Dict[str, Any]
    export_urls: List[Dict[str, str]] = field(default_factory=list)
    compliance: Dict[str, Any] = field(default_factory=dict)


class CrossPlatformEngine:
    """跨平台内容生成引擎（纯业务逻辑层，无 SSE、无 HTTP）
    提供 stream=True（流式）和 stream=False（同步）两种模式
    """

    def __init__(self) -> None:
        self.master_gen = MasterGenerator()
        self.platform_adaptor = PlatformAdaptor()
        self.compliance_scanner = ComplianceScanner()
        self.html_renderer = HtmlRenderer()
        self.profile_service = UserProfileService()
        self.storage = FileSystemStorage()
        self.export_service = ExportRecordService()
        self.resource_uploader = ResourceUploader()
        self.summarizer = ContentSummarizer()

    async def generate_stream(
        self,
        user_id: str,
        conversation_id: str,
        message: str,
        target_platforms: List[str],
        context: Dict[str, Any],
        session_history: List[Dict[str, Any]],
        request_id: str = "",
    ) -> AsyncIterator[PlatformChunk]:
        """流式模式：逐平台 yield PlatformChunk"""
        positioning = await self.profile_service.resolve_positioning(
            user_id, target_platforms[0] if target_platforms else "", context, session_history
        )

        master_content = await self.master_gen.generate(
            message=message,
            positioning=positioning,
            seed_topic=context.get("seed_topic"),
            user_position=context.get("user_position"),
            content_type=context.get("content_type", "图文"),
        )

        yield PlatformChunk(type="master", platform=None, content=master_content)

        registry = PlatformRegistry()
        content_type = context.get("content_type", "图文")

        for platform in target_platforms:
            version = await self.platform_adaptor.adapt(
                master_content=master_content,
                platform=platform,
                positioning=positioning,
                content_type=content_type,
            )

            text = version.get("title", "") + version.get("body", version.get("content", ""))
            warnings = self.compliance_scanner.scan(text, platform=platform)
            if warnings:
                version["compliance_warnings"] = warnings

            version = self._inject_platform_specific_fields(version, platform)

            version["summary"] = await self.summarizer.summarize(
                version, platform=platform
            )
            spec = registry.load(platform)
            version["platform_required_content"] = self._extract_required_content(
                spec, content_type
            )

            html = self.html_renderer.render(
                version, positioning, platform=platform, spec=spec, content_type=content_type
            )
            url = self.storage.save(request_id=request_id, platform=platform, html=html)
            version["export_url"] = url

            yield PlatformChunk(
                type="platform", platform=platform, content=version, warnings=warnings
            )

        # 母稿 HTML
        master_html = self.html_renderer.render(
            master_content, positioning, is_master=True, content_type=content_type
        )
        self.storage.save(request_id=request_id, platform=None, html=master_html)

    async def generate_sync(
        self,
        user_id: str,
        conversation_id: str,
        message: str,
        target_platforms: List[str],
        context: Dict[str, Any],
        session_history: List[Dict[str, Any]],
        request_id: str = "",
    ) -> ContentPipelineResult:
        """同步模式：返回完整的 ContentPipelineResult"""
        positioning = await self.profile_service.resolve_positioning(
            user_id, target_platforms[0] if target_platforms else "", context, session_history
        )

        master_content = await self.master_gen.generate(
            message=message,
            positioning=positioning,
            seed_topic=context.get("seed_topic"),
            user_position=context.get("user_position"),
            content_type=context.get("content_type", "图文"),
        )
        master_content["summary"] = await self.summarizer.summarize(
            master_content, platform=None
        )
        master_content["platform_required_content"] = None

        registry = PlatformRegistry()
        content_type = context.get("content_type", "图文")

        platform_versions: List[Dict[str, Any]] = []
        all_warnings: List[str] = []

        for platform in target_platforms:
            version = await self.platform_adaptor.adapt(
                master_content=master_content,
                platform=platform,
                positioning=positioning,
                content_type=content_type,
            )

            text = version.get("title", "") + version.get("body", version.get("content", ""))
            warnings = self.compliance_scanner.scan(text, platform=platform)
            if warnings:
                version["compliance_warnings"] = warnings
                all_warnings.extend(warnings)

            version = self._inject_platform_specific_fields(version, platform)

            version["summary"] = await self.summarizer.summarize(
                version, platform=platform
            )
            spec = registry.load(platform)
            version["platform_required_content"] = self._extract_required_content(
                spec, content_type
            )

            html = self.html_renderer.render(
                version, positioning, platform=platform, spec=spec, content_type=content_type
            )
            url = self.storage.save(request_id=request_id, platform=platform, html=html)
            version["export_url"] = url

            platform_versions.append(version)

        # 母稿 HTML
        master_html = self.html_renderer.render(
            master_content, positioning, is_master=True, content_type=content_type
        )
        master_url = self.storage.save(request_id=request_id, platform=None, html=master_html)

        # 合规汇总
        compliance = self._aggregate_compliance(all_warnings)

        export_urls = [
            {
                "platform": "master",
                "url": master_url,
                "variant": "master",
                "title": master_content.get("title", ""),
                "summary": master_content.get("summary", ""),
                "platform_required_content": master_content.get(
                    "platform_required_content"
                ),
            },
        ]
        for v in platform_versions:
            export_urls.append({
                "platform": v["platform"],
                "url": v["export_url"],
                "variant": "platform_adapt",
                "title": v.get("title", ""),
                "summary": v.get("summary", ""),
                "platform_required_content": v.get("platform_required_content"),
            })

        # 上传 HTML 到 OSS，获取真实 URL
        url_map = {u["platform"]: u["url"] for u in export_urls}
        uploaded = await self.resource_uploader.upload_batch(url_map)
        for u in export_urls:
            real_url = uploaded.get(u["platform"])
            if real_url and real_url != u["url"]:
                u["url"] = real_url
                # 同步更新 platform_versions 中的 export_url
                if u["platform"] == "master":
                    master_content["export_url"] = real_url
                else:
                    for v in platform_versions:
                        if v.get("platform") == u["platform"]:
                            v["export_url"] = real_url

        result = ContentPipelineResult(
            master_content=master_content,
            platform_versions=platform_versions,
            positioning=positioning,
            export_urls=export_urls,
            compliance=compliance,
        )

        # 异步保存元数据到数据库（不阻塞返回）
        try:
            await self.export_service.save_exports(
                user_id=user_id,
                conversation_id=conversation_id,
                request_id=request_id,
                export_urls=export_urls,
                platform_versions=platform_versions,
                master_content=master_content,
            )
        except Exception:
            logger.exception("Failed to persist export metadata")

        return result

    def _inject_platform_specific_fields(
        self, version: Dict[str, Any], platform: str
    ) -> Dict[str, Any]:
        """补充平台特定字段"""
        if platform == "xiaohongshu":
            version["pic_count_tip"] = "6-9 张"
            version["pic_ratio"] = "3:4"
        elif platform == "douyin":
            version["duration_tip"] = "15-60 秒"
        elif platform == "bilibili":
            version["danmu_prompt"] = "在关键转折点设置弹幕互动引导"
        return version

    def _extract_required_content(
        self, spec: Any, content_type: str
    ) -> Dict[str, Any]:
        """从平台规范中提取当前内容类型下 required=true 的字段及其规范。"""
        fmt = spec.content_formats.get(content_type, {}) if spec else {}
        result: Dict[str, Any] = {}
        for field_name, cfg in fmt.items():
            if isinstance(cfg, dict) and cfg.get("required") is True:
                result[field_name] = dict(cfg)
        return result

    def _aggregate_compliance(self, warnings: List[str]) -> Dict[str, Any]:
        """汇总所有平台的合规扫描结果"""
        if not warnings:
            return {
                "risk_level": "low",
                "risk_categories": ["none"],
                "violations": [],
                "suggestion": "未发现明显违规词，内容可直接使用。",
                "report_md": "## ✅ 合规审查结果\n\n- **风险等级**：low\n- **风险类别**：none\n- **命中违规词**：无\n- **建议**：未发现明显违规词",
            }

        categories = set()
        violations = []
        for w in warnings:
            parts = w.split("类禁用词")
            if len(parts) > 1:
                cat = parts[0].replace("命中", "").strip()
                categories.add(cat)
                term_part = parts[1].split("→")[0].strip().replace("：", "")
                violations.append({
                    "term": term_part,
                    "category": cat,
                    "suggestion": parts[1].split("→")[1].strip() if "→" in parts[1] else "",
                })

        return {
            "risk_level": "medium" if len(warnings) <= 3 else "high",
            "risk_categories": list(categories),
            "violations": violations,
            "suggestion": f"发现 {len(warnings)} 处合规风险，请根据建议修改。",
            "report_md": f"## ⚠️ 合规审查结果\n\n- **风险等级**：{'medium' if len(warnings) <= 3 else 'high'}\n- **风险类别**：{', '.join(categories)}\n- **命中违规词**：{len(warnings)} 处\n- **建议**：请根据下方详细提示修改",
        }
