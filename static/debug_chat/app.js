(function () {
  "use strict";

  /* ===== 常量 ===== */
  const LS_USER = "lumina_debug_user_id";
  const LS_CONV = "lumina_debug_conversation_id";
  const LS_CAP = "lumina_debug_capability";
  const LS_PLATFORM = "lumina_debug_platform";
  const LS_THEME = "lumina_debug_theme";
  const LS_CTX = "lumina_debug_context_json";

  const CAPABILITIES = [
    { id: "system_chat", label: "系统对话(编排API)", apiService: "system-chat" },
    { id: "content_direction_ranking", label: "内容方向榜单", apiService: "content-ranking" },
    { id: "positioning_case_library", label: "定位决策案例库", apiService: "positioning", mode: "case" },
    { id: "content_positioning_matrix", label: "内容定位矩阵", apiService: "positioning", mode: "matrix" },
    { id: "weekly_decision_snapshot", label: "每周决策快照", apiService: "weekly-snapshot" },
  ];

  const SYSTEM_CHAT = "system_chat";
  const POSITIONING_CASE = "positioning_case_library";
  const POSITIONING_MATRIX = "content_positioning_matrix";
  const POSITIONING_IDS = new Set([POSITIONING_CASE, POSITIONING_MATRIX]);

  /* ===== DOM 引用 ===== */
  const $ = (id) => document.getElementById(id);
  const messagesEl = $("messages");
  const memJsonEl = $("memJson");
  const memCountEl = $("memCount");
  const statusEl = $("status");
  const inputEl = $("input");
  const capabilityEl = $("service");
  const positioningModeEl = $("positioningMode");
  const platformEl = $("platform");
  const contextFieldWrap = $("contextFieldWrap");
  const positioningModeWrap = $("positioningModeWrap");
  const contextJsonEl = $("contextJson");
  const debugPanel = $("debugPanel");

  let abortCtrl = null;
  let loadedCount = 0;
  let hasMoreEarlier = false;

  /* ===== 主题 ===== */
  function loadTheme() {
    const t = localStorage.getItem(LS_THEME) || "light";
    document.documentElement.setAttribute("data-theme", t === "dark" ? "dark" : "light");
  }

  function toggleTheme() {
    const cur = document.documentElement.getAttribute("data-theme");
    const next = cur === "light" ? "dark" : "light";
    localStorage.setItem(LS_THEME, next);
    document.documentElement.setAttribute("data-theme", next);
  }

  /* ===== Markdown 渲染 ===== */
  let _md = null;
  try {
    if (typeof marked !== 'undefined') {
      _md = marked.setOptions({
        breaks: true,
        gfm: true,
      });
    }
  } catch (e) {
    console.warn('marked not available, fallback to plain text');
  }

  function renderMarkdown(text) {
    if (!_md || !text) return text || '';
    try {
      return _md.parse(text);
    } catch (e) {
      return text;
    }
  }

  function setBodyContent(el, text) {
    if (!el) return;
    if (_md && text) {
      el.innerHTML = renderMarkdown(text);
    } else {
      el.textContent = text || '';
    }
  }

  /* ===== 工具函数 ===== */
  function randomId(prefix) {
    try {
      if (typeof crypto !== "undefined" && crypto.randomUUID) {
        return prefix + crypto.randomUUID().replace(/-/g, "").slice(0, 16);
      }
    } catch (e) { /* fall through */ }
    return prefix + Math.random().toString(36).slice(2, 14);
  }

  function ensureIds() {
    const uidInput = $("userId");
    const cidInput = $("convId");
    if (!uidInput.value.trim()) uidInput.value = localStorage.getItem(LS_USER) || randomId("u_");
    if (!cidInput.value.trim()) cidInput.value = localStorage.getItem(LS_CONV) || randomId("c_");
    persistIds();
  }

  function persistIds() {
    localStorage.setItem(LS_USER, $("userId").value.trim());
    localStorage.setItem(LS_CONV, $("convId").value.trim());
    localStorage.setItem(LS_CAP, capabilityEl.value);
    localStorage.setItem(LS_PLATFORM, platformEl.value.trim());
    localStorage.setItem(LS_CTX, contextJsonEl.value);
  }

  function getSelectedCapability() {
    return CAPABILITIES.find((c) => c.id === capabilityEl.value) || CAPABILITIES[0];
  }

  function updateFieldVisibility() {
    const cap = getSelectedCapability();
    contextFieldWrap.classList.toggle("hidden", cap.id !== SYSTEM_CHAT);
    positioningModeWrap.classList.toggle("hidden", !POSITIONING_IDS.has(cap.id));
    if (POSITIONING_IDS.has(cap.id) && positioningModeEl) {
      positioningModeEl.value = cap.mode || "case";
    }
  }

  function initCapabilities() {
    capabilityEl.innerHTML = "";
    const saved = localStorage.getItem(LS_CAP);
    for (const c of CAPABILITIES) {
      const opt = document.createElement("option");
      opt.value = c.id;
      opt.textContent = c.label;
      capabilityEl.appendChild(opt);
    }
    if (saved && [...capabilityEl.options].some((o) => o.value === saved)) {
      capabilityEl.value = saved;
    }
    updateFieldVisibility();
  }

  function getClient(contextOverride) {
    const cap = getSelectedCapability();
    let ctx = contextOverride;
    if (ctx === undefined) {
      try { ctx = JSON.parse(contextJsonEl.value.trim() || "{}"); }
      catch { ctx = {}; }
    }
    return new LuminaChatClient({
      userId: $("userId").value.trim(),
      conversationId: $("convId").value.trim(),
      service: cap.apiService,
      platform: platformEl.value.trim() || null,
      context: ctx,
    });
  }

  /* ===== 气泡渲染 ===== */
  function createBubble(role, meta) {
    const div = document.createElement("div");
    div.className = `bubble ${role}`;

    // 角色标记
    const badge = document.createElement("div");
    badge.className = "role-badge";
    badge.textContent = role === "user" ? "你" : "Lumina";
    div.appendChild(badge);

    // 正文容器（内容由 setBodyContent 填充）
    const body = document.createElement("div");
    body.className = "body";
    div.appendChild(body);

    // 时间戳
    if (meta) {
      const ts = document.createElement("div");
      ts.className = "ts";
      ts.textContent = meta;
      div.appendChild(ts);
    }

    return div;
  }

  function appendBubble(role, text, meta) {
    const div = createBubble(role, meta);
    const body = div.querySelector('.body');
    messagesEl.appendChild(div);
    messagesEl.scrollTop = messagesEl.scrollHeight;
    // 渲染 markdown
    setBodyContent(body, text);
    return body;
  }

  function setStatus(t) {
    statusEl.textContent = t || "";
  }

  /* ===== 历史消息 ===== */
  function historyBubble(m) {
    if (m.role !== "user" && m.role !== "assistant") return null;
    const text = typeof m.content === "string" ? m.content : JSON.stringify(m.content);
    const ts = m.ts ? m.ts.replace("T", " ").slice(0, 19) : "";
    const div = createBubble(m.role, ts);
    if (m.ts) div.dataset.ts = `${m.role}|${m.ts}`;
    // 渲染历史消息 markdown
    const body = div.querySelector('.body');
    setBodyContent(body, text);
    return div;
  }

  function updateLoadEarlierVisibility() {
    const wrap = $("loadEarlierWrap");
    if (wrap) wrap.style.display = hasMoreEarlier ? "flex" : "none";
  }

  async function refreshMemory() {
    ensureIds();
    try {
      const { messages, total } = await getClient().loadHistory({ limit: 200 });
      memJsonEl.textContent = JSON.stringify(messages, null, 2);
      memCountEl.textContent = `${messages.length}/${total} 条`;
    } catch (e) {
      memJsonEl.textContent = JSON.stringify({ error: String(e) }, null, 2);
      memCountEl.textContent = "0 条";
    }
  }

  async function loadHistoryIntoChat() {
    ensureIds();
    [...messagesEl.querySelectorAll(".bubble")].forEach((el) => el.remove());
    loadedCount = 0;
    hasMoreEarlier = false;
    try {
      const { messages, hasMore } = await getClient().loadHistory();
      for (const m of messages) {
        const div = historyBubble(m);
        if (!div) continue;
        messagesEl.appendChild(div);
        loadedCount += 1;
      }
      hasMoreEarlier = hasMore;
      messagesEl.scrollTop = messagesEl.scrollHeight;
    } catch (e) {
      appendBubble("assistant", `历史加载失败：${e.message}`);
    }
    updateLoadEarlierVisibility();
    refreshMemory();
  }

  async function loadEarlier() {
    if (!hasMoreEarlier) return;
    const existing = new Set(
      [...messagesEl.querySelectorAll(".bubble[data-ts]")].map((el) => el.dataset.ts)
    );
    setStatus("加载更早消息…");
    try {
      const anchor = $("loadEarlierWrap").nextSibling;
      const { messages, hasMore } = await getClient().loadHistory({ offset: loadedCount });
      let added = 0;
      for (const m of messages) {
        const div = historyBubble(m);
        if (!div) continue;
        if (div.dataset.ts && existing.has(div.dataset.ts)) continue;
        messagesEl.insertBefore(div, anchor);
        added += 1;
      }
      loadedCount += added;
      hasMoreEarlier = hasMore;
      setStatus(added ? `已加载 ${added} 条更早消息` : "没有更多消息");
    } catch (e) {
      setStatus("加载更早失败：" + e.message);
    }
    updateLoadEarlierVisibility();
  }

  /* ===== 发送消息 ===== */
  async function send() {
    const text = inputEl.value.trim();
    if (!text) return;
    ensureIds();
    persistIds();

    if (abortCtrl) abortCtrl.abort();
    const ctrl = new AbortController();
    abortCtrl = ctrl;

    const cap = getSelectedCapability();

    // JSON 校验
    let ctx = {};
    if (cap.id === SYSTEM_CHAT) {
      const raw = contextJsonEl.value.trim();
      if (raw) {
        try {
          ctx = JSON.parse(raw);
          if (ctx === null || typeof ctx !== "object" || Array.isArray(ctx)) {
            throw new Error("context 须为 JSON 对象");
          }
        } catch (e) {
          appendBubble("user", text);
          appendBubble("assistant", "上下文 JSON 无效：" + e.message);
          setStatus("JSON 错误");
          abortCtrl = null;
          return;
        }
      }
    }

    const chat = getClient(ctx);
    appendBubble("user", text);
    inputEl.value = "";
    autoResize();

    const asstBody = appendBubble("assistant", "…");
    let full = "";
    let persistedTurns = 1;

    $("btnSend").disabled = true;
    $("btnStop").disabled = false;
    setStatus("生成中…");

    try {
      await chat.send(text, {
        onEvent: (ev) => {
          if (ev.type === "platform_chunk" && ev.content) {
            full += ev.content;
            setBodyContent(asstBody, full);
            scrollToBottom();
          }
        },
        onStart: () => {
          // 不展示 request_id / 服务名等调试信息
        },
        onDelta: (t) => {
          full += t;
          setBodyContent(asstBody, full);
          scrollToBottom();
        },
        onDone: (ev) => {
          persistedTurns = 2;
          const bits = [];
          if (typeof ev.reply_ms === "number") bits.push(`${ev.reply_ms}ms`);
          if (ev.usage && typeof ev.usage === "object" && ev.usage.total_tokens) {
            bits.push(`${ev.usage.total_tokens} tokens`);
          }
          setStatus(bits.join(" · ") || "完成");
        },
        onError: (err) => {
          setBodyContent(asstBody, full + (full ? "\n\n" : "") + "[错误] " + (err.message || "unknown"));
          setStatus("模型错误");
        },
      }, { signal: ctrl.signal });

      if (ctrl.signal.aborted) {
        setBodyContent(asstBody, full || "（已停止）");
        setStatus("已停止");
      }
    } catch (e) {
      if (ctrl.signal.aborted) {
        setBodyContent(asstBody, full || "（已停止）");
        setStatus("已停止");
      } else {
        setBodyContent(asstBody, String(e));
        setStatus("异常");
      }
    } finally {
      $("btnSend").disabled = false;
      $("btnStop").disabled = true;
      abortCtrl = null;
      loadedCount += persistedTurns;
      await refreshMemory();
    }
  }

  function scrollToBottom() {
    messagesEl.scrollTop = messagesEl.scrollHeight;
  }

  function stop() {
    if (abortCtrl) abortCtrl.abort();
  }

  /* ===== Textarea 自适应高度 ===== */
  function autoResize() {
    inputEl.style.height = "auto";
    inputEl.style.height = Math.min(inputEl.scrollHeight, 120) + "px";
  }

  /* ===== 快捷标签 ===== */
  function handleTagClick(e) {
    const btn = e.currentTarget;
    const text = btn.dataset.text;
    if (text) {
      inputEl.value = text;
      autoResize();
      inputEl.focus();
      send();
    }
  }

  /* ===== 调试面板折叠 ===== */
  let panelCollapsed = false;
  function togglePanel() {
    panelCollapsed = !panelCollapsed;
    document.querySelector(".layout").classList.toggle("panel-collapsed", panelCollapsed);
  }

  /* ===== 事件绑定 ===== */
  $("btn-theme").addEventListener("click", toggleTheme);
  $("btnNewUser").addEventListener("click", () => {
    $("userId").value = randomId("u_");
    persistIds();
    loadHistoryIntoChat();
  });
  $("btnNewConv").addEventListener("click", () => {
    $("convId").value = randomId("c_");
    persistIds();
    loadHistoryIntoChat();
  });
  $("btnClearMem").addEventListener("click", async () => {
    ensureIds();
    await getClient().clear();
    loadedCount = 0;
    hasMoreEarlier = false;
    [...messagesEl.querySelectorAll(".bubble")].forEach((el) => el.remove());
    updateLoadEarlierVisibility();
    await refreshMemory();
    setStatus("记忆已清空");
  });
  $("btnRefreshMem").addEventListener("click", refreshMemory);
  $("btnLoadEarlier").addEventListener("click", loadEarlier);
  $("btnTogglePanel").addEventListener("click", togglePanel);

  capabilityEl.addEventListener("change", () => {
    updateFieldVisibility();
    persistIds();
    loadHistoryIntoChat();
  });
  positioningModeEl.addEventListener("change", persistIds);
  contextJsonEl.addEventListener("blur", persistIds);
  platformEl.addEventListener("change", persistIds);
  $("userId").addEventListener("blur", persistIds);
  $("convId").addEventListener("blur", persistIds);

  $("btnSend").addEventListener("click", send);
  $("btnStop").addEventListener("click", stop);

  inputEl.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  });

  // Textarea 自适应
  inputEl.addEventListener("input", autoResize);

  // 快捷标签
  document.querySelectorAll(".tag").forEach((el) => {
    el.addEventListener("click", handleTagClick);
  });

  /* ===== 初始化 ===== */
  loadTheme();
  $("userId").value = localStorage.getItem(LS_USER) || "";
  $("convId").value = localStorage.getItem(LS_CONV) || "";
  platformEl.value = localStorage.getItem(LS_PLATFORM) || "";
  contextJsonEl.value = localStorage.getItem(LS_CTX) || "";

  initCapabilities();
  ensureIds();
  loadHistoryIntoChat().catch((e) => {
    memJsonEl.textContent = JSON.stringify({ error: String(e) }, null, 2);
  });
})();
