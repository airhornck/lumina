/**
 * Layer1 意图闸（OpenClaw 扩展内，在调 Python 之前执行）
 * 规则需与 Python `apps/orchestra/.../core.py` 中
 * `_OFF_TOPIC_CHITCHAT` / `_MARKETING_ANCHOR` 保持同步。
 */

const MARKETING_ANCHOR =
  /营销|账号|小红书|抖音|b站|bilibili|视频号|快手|内容|涨粉|流量|转化|直播|笔记|种草|品牌|投放|达人|带货|私域|公域|爆款|钩子|选题|文案|脚本/i;

const OFF_TOPIC_CHITCHAT =
  /天气|气温|下雨|下雪|刮风|台风|雾霾|冷不冷|热不热|几点了|星期几|周几|今天是|讲个笑话|讲个段子|讲故事|唱首歌|你会什么|你是谁做的|晚饭吃|午饭吃|早餐吃|外卖吃|睡不着|累死了/i;

export type IntentGateResult =
  | { pass: true }
  | {
      pass: false;
      reason: "off_topic";
      /** 建议模型转述给用户 */
      reply: string;
      /** 给模型的系统级提示 */
      agentNote: string;
    };

export function gateMarketingHubInput(userInput: string): IntentGateResult {
  const t = (userInput ?? "").trim();
  if (!t) {
    return {
      pass: false,
      reason: "off_topic",
      reply: "没有收到有效内容。如需营销相关帮助，请说明平台、目标或具体问题。",
      agentNote: "user_input 为空，不要重试本工具；请让用户补充问题。",
    };
  }

  if (OFF_TOPIC_CHITCHAT.test(t) && !MARKETING_ANCHOR.test(t)) {
    return {
      pass: false,
      reason: "off_topic",
      reply:
        "我（Lumina 营销中枢）只处理小红书/抖音等内容营销与增长问题，不负责天气、作息、笑话等生活类话题。这类问题请你直接回答用户即可。",
      agentNote:
        "本次调用已被 Lumina 意图闸拦截（离题/生活类）。请直接用你的通用能力回答用户，不要再次调用 marketing_intelligence_hub。",
    };
  }

  return { pass: true };
}

export function isIntentGateDisabled(): boolean {
  const v = (process.env.LUMINA_DISABLE_INTENT_GATE ?? "").trim().toLowerCase();
  return v === "1" || v === "true" || v === "yes";
}
