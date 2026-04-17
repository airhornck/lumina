(function () {
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

  let abortCtrl = null;

  function loadTheme() {
    const t = localStorage.getItem(LS_THEME) || "dark";
    document.documentElement.setAttribute("data-theme", t === "light" ? "light" : "dark");
  }

  function toggleTheme() {
    const cur = document.documentElement.getAttribute("data-theme");
    const next = cur === "light" ? "dark" : "light";
    localStorage.setItem(LS_THEME, next === "light" ? "light" : "dark");
    document.documentElement.setAttribute("data-theme", next);
  }

  function randomId(prefix) {
    try {
      if (typeof crypto !== "undefined" && crypto.randomUUID) {
        return prefix + crypto.randomUUID().replace(/-/g, "").slice(0, 16);
      }
    } catch (e) {}
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
      opt.textContent = `${c.label} (${c.id})`;
      capabilityEl.appendChild(opt);
    }
    if (saved && [...capabilityEl.options].some((o) => o.value === saved)) {
      capabilityEl.value = saved;
    }
    updateFieldVisibility();
  }

  async function refreshMemory() {
    ensureIds();
    const uid = $("userId").value.trim();
    const cid = $("convId").value.trim();
    const cap = getSelectedCapability();
    const svc = cap.apiService;
    const url = `/api/v1/services/${encodeURIComponent(svc)}/memory?user_id=${encodeURIComponent(uid)}&conversation_id=${encodeURIComponent(cid)}`;
    try {
      const r = await fetch(url);
      const data = await r.json();
      memJsonEl.textContent = JSON.stringify(data.messages || [], null, 2);
      memCountEl.textContent = `${data.count ?? 0} 条`;
    } catch (e) {
      memJsonEl.textContent = JSON.stringify({ error: String(e) }, null, 2);
      memCountEl.textContent = "0 条";
    }
  }

  function appendBubble(role, text, meta) {
    const div = document.createElement("div");
    div.className = `bubble ${role}`;
    if (meta) {
      const m = document.createElement("div");
      m.className = "meta";
      m.textContent = meta;
      div.appendChild(m);
    }
    const body = document.createElement("div");
    body.textContent = text;
    div.appendChild(body);
    messagesEl.appendChild(div);
    messagesEl.scrollTop = messagesEl.scrollHeight;
    return body;
  }

  function setStatus(t) {
    statusEl.textContent = t || "";
  }

  async function send() {
    const text = inputEl.value.trim();
    if (!text) return;
    ensureIds();
    persistIds();

    if (abortCtrl) abortCtrl.abort();
    abortCtrl = new AbortController();

    const cap = getSelectedCapability();
    const svc = cap.apiService;
    const svcLabel = capabilityEl.selectedOptions[0]?.textContent || svc;
    appendBubble("user", text, `user · ${svcLabel}`);
    inputEl.value = "";

    const asstBody = appendBubble("assistant", "", "assistant · 生成中…");
    let full = "";

    $("btnSend").disabled = true;
    $("btnStop").disabled = false;
    setStatus("流式接收中…");

    const payload = {
      user_id: $("userId").value.trim(),
      conversation_id: $("convId").value.trim(),
      message: text,
    };
    const plat = platformEl.value.trim();
    if (plat) payload.platform = plat;

    if (cap.id === SYSTEM_CHAT) {
      const raw = contextJsonEl.value.trim();
      if (raw) {
        try {
          payload.context = JSON.parse(raw);
          if (
            payload.context === null ||
            typeof payload.context !== "object" ||
            Array.isArray(payload.context)
          ) {
            throw new Error("context 须为 JSON 对象");
          }
        } catch (e) {
          asstBody.textContent = "编排上下文 JSON 无效：" + e.message;
          setStatus("JSON 错误");
          $("btnSend").disabled = false;
          $("btnStop").disabled = true;
          abortCtrl = null;
          return;
        }
      } else {
        payload.context = {};
      }
    }

    if (POSITIONING_IDS.has(cap.id)) {
      payload.mode = cap.mode || positioningModeEl.value;
    }

    try {
      const res = await fetch(`/api/v1/services/${encodeURIComponent(svc)}/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
        signal: abortCtrl.signal,
      });

      if (!res.ok) {
        const errText = await res.text();
        asstBody.textContent = `HTTP ${res.status}: ${errText}`;
        setStatus("请求失败");
        return;
      }

      const reader = res.body.getReader();
      const dec = new TextDecoder();
      let buf = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buf += dec.decode(value, { stream: true });

        let idx;
        while ((idx = buf.indexOf("\n\n")) >= 0) {
          const line = buf.slice(0, idx).trim();
          buf = buf.slice(idx + 2);
          if (!line.startsWith("data:")) continue;
          const jsonStr = line.slice(5).trim();
          let ev;
          try {
            ev = JSON.parse(jsonStr);
          } catch {
            continue;
          }
          if (ev.type === "delta" && ev.text) {
            full += ev.text;
            asstBody.textContent = full;
            messagesEl.scrollTop = messagesEl.scrollHeight;
          } else if (ev.type === "error") {
            asstBody.textContent = full + (full ? "\n\n" : "") + "[错误] " + (ev.message || "unknown");
            setStatus("模型错误");
          } else if (ev.type === "done") {
            setStatus("完成");
          } else if (ev.type === "start") {
            let meta = `assistant · ${ev.service || ""}`;
            if (ev.via) meta += ` · ${ev.via}`;
            if (ev.mode) meta += ` · ${ev.mode}`;
            asstBody.parentElement.querySelector(".meta").textContent = meta;
          }
        }
      }
    } catch (e) {
      if (e.name === "AbortError") {
        asstBody.textContent = full + (full ? "" : "（已停止）");
        setStatus("已停止");
      } else {
        asstBody.textContent = String(e);
        setStatus("异常");
      }
    } finally {
      $("btnSend").disabled = false;
      $("btnStop").disabled = true;
      abortCtrl = null;
      await refreshMemory();
    }
  }

  function stop() {
    if (abortCtrl) abortCtrl.abort();
  }

  $("btn-theme").addEventListener("click", toggleTheme);
  $("btnNewUser").addEventListener("click", () => {
    $("userId").value = randomId("u_");
    persistIds();
    refreshMemory();
  });
  $("btnNewConv").addEventListener("click", () => {
    $("convId").value = randomId("c_");
    persistIds();
    messagesEl.innerHTML = "";
    refreshMemory();
  });
  $("btnClearMem").addEventListener("click", async () => {
    ensureIds();
    const uid = $("userId").value.trim();
    const cid = $("convId").value.trim();
    const cap = getSelectedCapability();
    const svc = cap.apiService;
    await fetch(
      `/api/v1/services/${encodeURIComponent(svc)}/memory?user_id=${encodeURIComponent(uid)}&conversation_id=${encodeURIComponent(cid)}`,
      { method: "DELETE" }
    );
    messagesEl.innerHTML = "";
    await refreshMemory();
    setStatus("记忆已清空");
  });
  $("btnRefreshMem").addEventListener("click", () => refreshMemory());
  capabilityEl.addEventListener("change", () => {
    updateFieldVisibility();
    persistIds();
    messagesEl.innerHTML = "";
    refreshMemory();
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

  loadTheme();
  $("userId").value = localStorage.getItem(LS_USER) || "";
  $("convId").value = localStorage.getItem(LS_CONV) || "";
  platformEl.value = localStorage.getItem(LS_PLATFORM) || "";
  contextJsonEl.value = localStorage.getItem(LS_CTX) || "";

  initCapabilities();
  ensureIds();
  refreshMemory().catch((e) => {
    memJsonEl.textContent = JSON.stringify({ error: String(e) }, null, 2);
  });
})();
