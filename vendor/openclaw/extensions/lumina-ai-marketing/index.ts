import { Type } from "@sinclair/typebox";
import type { AnyAgentTool, OpenClawPluginApi } from "openclaw/plugin-sdk/core";
import { emptyPluginConfigSchema } from "openclaw/plugin-sdk/core";

import { gateMarketingHubInput, isIntentGateDisabled } from "./intent-gate.js";

type AgentToolResult = {
  content: Array<{ type: string; text: string }>;
  details?: unknown;
};

function jsonResult(payload: unknown): AgentToolResult {
  return {
    content: [{ type: "text", text: JSON.stringify(payload, null, 2) }],
    details: payload,
  };
}

/** Development_plan_v2：单一入口，转发至 Python 多 Agent 中枢。 */
const MarketingHubSchema = Type.Object(
  {
    user_input: Type.String({
      description: "用户当前轮输入（原始文本）",
    }),
    user_id: Type.Optional(Type.String({ description: "用户隔离 id" })),
    platform: Type.Optional(
      Type.String({
        description: "平台：xiaohongshu | douyin | bilibili 等",
      }),
    ),
    session_history: Type.Optional(
      Type.Array(Type.Record(Type.String(), Type.Unknown()), {
        description: "最近若干条会话摘要（可选）",
      }),
    ),
    context: Type.Optional(
      Type.Record(Type.String(), Type.Unknown(), {
        description: "额外上下文：metrics、industry、account_url 等",
      }),
    ),
  },
  { additionalProperties: false },
);

async function executeMarketingHub(
  _toolCallId: string,
  params: {
    user_input: string;
    user_id?: string;
    platform?: string;
    session_history?: Record<string, unknown>[];
    context?: Record<string, unknown>;
  },
): Promise<AgentToolResult> {
  if (!isIntentGateDisabled()) {
    const gate = gateMarketingHubInput(params.user_input);
    if (!gate.pass) {
      return jsonResult({
        ok: true,
        source: "openclaw_intent_gate",
        passed: false,
        gate_reason: gate.reason,
        reply: gate.reply,
        agent_note: gate.agentNote,
      });
    }
  }

  const base = (process.env.LUMINA_PYTHON_URL ?? "http://127.0.0.1:8000").replace(/\/$/, "");
  const url = `${base}/api/v1/marketing/hub`;
  const body = {
    user_input: params.user_input,
    user_id: params.user_id ?? "anonymous",
    session_history: params.session_history ?? [],
    platform: params.platform,
    context: params.context ?? {},
  };
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const text = await res.text();
  let data: unknown;
  try {
    data = JSON.parse(text) as unknown;
  } catch {
    data = { raw: text };
  }
  if (!res.ok) {
    return jsonResult({
      ok: false,
      status: res.status,
      error: data,
    });
  }
  return jsonResult(data);
}

const plugin = {
  id: "lumina-ai-marketing",
  name: "Lumina Marketing Intelligence Hub",
  description:
    "Layer1 Bridge：工具 marketing_intelligence_hub → Python 编排中枢（Orchestra）→ MCP Skill Hub。环境变量 LUMINA_PYTHON_URL（默认 http://127.0.0.1:8000）。",
  configSchema: emptyPluginConfigSchema(),
  register(api: OpenClawPluginApi) {
    api.registerTool(
      {
        name: "marketing_intelligence_hub",
        label: "Marketing Intelligence Hub",
        description:
          "【仅营销场景】用户明确讨论小红书/抖音/内容增长/账号/流量/选题/文案/脚本/方法论等时调用。天气、笑话、吃饭、作息等生活闲聊不要调用本工具——请你自己直接回答。传入 user_input；可选 platform、session_history、context。",
        parameters: MarketingHubSchema,
        execute: executeMarketingHub,
      } as unknown as AnyAgentTool,
      { optional: true },
    );
  },
};

export default plugin;
