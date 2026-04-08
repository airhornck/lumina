(function () {
  const LS_USER = "lumina_debug_user_id";
  const LS_CONV = "lumina_debug_conversation_id";
  const LS_CAP = "lumina_debug_capability";
  const LS_PLATFORM = "lumina_debug_platform";
  const LS_THEME = "lumina_debug_theme";
  const LS_CTX = "lumina_debug_context_json";

  const SYSTEM_CHAT = "system_chat";

  const $ = (id) => document.getElementById(id);

  const messagesEl = $("messages");
  const memJsonEl = $("memJson");
  const memCountEl = $("memCount");
  const statusEl = $("status");
  const inputEl = $("input");
  const capabilityEl = $("capability");
  const platformEl = $("platform");
  const contextFieldWrap = $("contextFieldWrap");
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
    if (crypto.randomUUID) return prefix + crypto.randomUUID().replace(/-/g, "").slice(0, 16);
    return prefix + Math.random().toString(36).slice(2, 14);
  }

  function ensureIds() {
    if (!$("userId").value.trim()) $("userId").value = localStorage.getItem(LS_USER) || randomId("u_");
    if (!$("convId").value.trim()) $("convId").value = localStorage.getItem(LS_CONV) || randomId("c_");
    persistIds();
  }

  function persistIds() {
    localStorage.setItem(LS_USER, $("userId").value.trim());
    localStorage.setItem(LS_CONV, $("convId").value.trim());
    localStorage.setItem(LS_CAP, capabilityEl.value);
    localStorage.setItem(LS_PLATFORM, platformEl.value.trim());
    localStorage.setItem(LS_CTX, contextJsonEl.value);
  }

  function updateContextFieldVisibility() {
    const on = capabilityEl.value === SYSTEM_CHAT;
    contextFieldWrap.classList.toggle("hidden", !on);
  }

  async function loadCapabilities() {
    const r = await fetch("/api/v1/debug/chat/capabilities");
    const data = await r.json();
    capabilityEl.innerHTML = "";
    const saved = localStorage.getItem(LS_CAP);
    for (const c of data.capabilities || []) {
      const opt = document.createElement("option");
      opt.value = c.id;
      opt.textContent = `${c.label} (${c.id})`;
      capabilityEl.appendChild(opt);
    }
    if (saved && [...capabilityEl.options].some((o) => o.value === saved)) {
      capabilityEl.value = saved;
    }
    updateContextFieldVisibility();
  }

  async function refreshMemory() {
    ensureIds();
    const uid = $("userId").value.trim();
    const cid = $("convId").value.trim();
    const url = `/api/v1/debug/chat/memory?user_id=${encodeURIComponent(uid)}&conversation_id=${encodeURIComponent(cid)}`;
    const r = await fetch(url);
    const data = await r.json();
    memJsonEl.textContent = JSON.stringify(data.messages || [], null, 2);
    memCountEl.textContent = `${data.count ?? 0} 条`;
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

    appendBubble("user", text, `user · ${capabilityEl.selectedOptions[0]?.textContent || ""}`);
    inputEl.value = "";

    const asstBody = appendBubble("assistant", "", "assistant · 生成中…");
    let full = "";

    $("btnSend").disabled = true;
    $("btnStop").disabled = false;
    setStatus("流式接收中…");

    const payload = {
      capability: capabilityEl.value,
      user_id: $("userId").value.trim(),
      conversation_id: $("convId").value.trim(),
      message: text,
    };
    const plat = platformEl.value.trim();
    if (plat) payload.platform = plat;

    if (capabilityEl.value === SYSTEM_CHAT) {
      const raw = contextJsonEl.value.trim();
      if (raw) {
        try {
          payload.hub_context = JSON.parse(raw);
          if (
            payload.hub_context === null ||
            typeof payload.hub_context !== "object" ||
            Array.isArray(payload.hub_context)
          ) {
            throw new Error("hub_context 须为 JSON 对象");
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
        payload.hub_context = {};
      }
    }

    try {
      const res = await fetch("/api/v1/debug/chat/stream", {
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
            let meta = `assistant · ${ev.capability || ""}`;
            if (ev.via) meta += ` · ${ev.via}`;
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
    await fetch(
      `/api/v1/debug/chat/memory?user_id=${encodeURIComponent(uid)}&conversation_id=${encodeURIComponent(cid)}`,
      { method: "DELETE" }
    );
    messagesEl.innerHTML = "";
    await refreshMemory();
    setStatus("记忆已清空");
  });
  $("btnRefreshMem").addEventListener("click", () => refreshMemory());
  capabilityEl.addEventListener("change", () => {
    updateContextFieldVisibility();
    persistIds();
  });
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

  loadCapabilities()
    .then(() => {
      ensureIds();
      return refreshMemory();
    })
    .catch((e) => {
      memJsonEl.textContent = JSON.stringify({ error: String(e) }, null, 2);
    });
})();
