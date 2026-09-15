/**
 * LuminaChatClient — Lumina 对话能力前端 SDK
 * 封装：历史加载（GET memory）+ SSE 流式对话（POST stream）+ 清除历史（DELETE memory）
 *
 * 底层 HTTP 协议：docs/CONVERSATION_HISTORY_API.md
 * 对接方案：docs/CONVERSATION_HISTORY_SOLUTION.md
 * 用法：
 *   const chat = new LuminaChatClient({ userId });
 *   const { messages, total, hasMore } = await chat.loadHistory();   // 默认最新 50 条
 *   await chat.send("你好", { onDelta: (t) => ..., onDone: () => ... });
 */
class LuminaChatClient {
  constructor(options) {
    const {
      userId,
      conversationId = "main",
      baseUrl = "",
      service = "system-chat",
      platform = null,
      context = {},
    } = options || {};
    if (!userId) throw new Error("LuminaChatClient: userId is required");
    this.baseUrl = baseUrl.replace(/\/$/, "");
    this.service = service;
    this.userId = userId;
    this.conversationId = conversationId;
    this.platform = platform;
    this.context = context;
  }

  _url(path) {
    return `${this.baseUrl}/api/v1/services/${this.service}${path}`;
  }

  _qs(extra = {}) {
    return new URLSearchParams({
      user_id: this.userId,
      conversation_id: this.conversationId,
      ...extra,
    }).toString();
  }

  /** 加载对话历史：默认最新 50 条；offset 用于向更早翻页 */
  async loadHistory({ limit = 50, offset = 0 } = {}) {
    const res = await fetch(this._url(`/memory?${this._qs({ limit, offset })}`));
    if (!res.ok) throw new Error(`loadHistory failed: HTTP ${res.status}`);
    const data = await res.json();
    return {
      messages: data.messages,   // [{role, content, ts, capability?}]，时间正序
      total: data.total,
      hasMore: data.has_more,
    };
  }

  /** 清除对话历史 */
  async clear() {
    const res = await fetch(this._url(`/memory?${this._qs()}`), { method: "DELETE" });
    if (!res.ok) throw new Error(`clear failed: HTTP ${res.status}`);
    return res.json(); // {ok, cleared, service}
  }

  /** 发送消息（SSE 流式），事件经 callbacks 分发 */
  async send(message, callbacks = {}, { signal } = {}) {
    const res = await fetch(this._url("/stream"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        user_id: this.userId,
        conversation_id: this.conversationId,
        message,
        ...(this.platform ? { platform: this.platform } : {}),
        context: this.context,
      }),
      signal,
    });
    if (!res.ok || !res.body) throw new Error(`send failed: HTTP ${res.status}`);

    const reader = res.body.getReader();
    const decoder = new TextDecoder("utf-8");
    let buffer = "";

    const dispatch = (evt) => {
      callbacks.onEvent?.(evt); // 透传原始事件（含平台自定义事件，便于调试/扩展）
      switch (evt.type) {
        case "start":            callbacks.onStart?.(evt); break;
        case "thinking_delta":   callbacks.onThinking?.(evt.text); break;
        case "tool_start":       callbacks.onToolStart?.(evt.tool, evt.args); break;
        case "tool_complete":    callbacks.onToolComplete?.(evt.tool, evt.ok, evt.elapsed_ms); break;
        case "assistant_delta":  callbacks.onDelta?.(evt.text); break;
        case "export_link":      callbacks.onExportLink?.(evt); break;
        case "compliance_report":callbacks.onCompliance?.(evt); break;
        case "done":             callbacks.onDone?.(evt); break;
        case "error":            callbacks.onError?.(new Error(evt.message), evt); break;
      }
    };

    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        let idx;
        while ((idx = buffer.indexOf("\n\n")) !== -1) {
          const block = buffer.slice(0, idx);
          buffer = buffer.slice(idx + 2);
          for (const line of block.split("\n")) {
            if (!line.startsWith("data:")) continue;
            const payload = line.slice(5).trim();
            if (!payload) continue;
            try { dispatch(JSON.parse(payload)); } catch { /* 忽略坏帧 */ }
          }
        }
      }
    } catch (e) {
      if (e?.name !== "AbortError") callbacks.onError?.(e);
    }
  }
}
