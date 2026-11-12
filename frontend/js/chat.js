import { state } from "./state.js";
import { escapeHtml, showToast, confirmDialog, setActiveNav } from "./ui.js";

function updateChatScope(knowledgeBaseId) {
  const knowledgeBase = state.knowledgeBases.find((item) => item.id === Number(knowledgeBaseId));
  const select = document.getElementById("chat-kb");
  const notice = document.getElementById("chat-scope");
  if (!knowledgeBase || !notice) {
    return;
  }
  state.chatKbId = knowledgeBase.id;
  if (select) {
    select.value = String(knowledgeBase.id);
  }
  const group = state.groups.find((item) => item.id === knowledgeBase.group_id);
  const scopeLabel = knowledgeBase.scope_type === "personal"
    ? "个人知识库 · 仅自己可见"
    : `${group ? group.name : "企业群组"} · 仅对群组成员开放`;
  notice.innerHTML = `<span aria-hidden="true">◈</span><span>当前仅检索：</span><strong>${escapeHtml(knowledgeBase.name)}</strong><span>· ${escapeHtml(scopeLabel)}</span>`;
}

function formatTime(value) {
  return value ? value.replace("T", " ").slice(0, 16) : "";
}

function renderAnswerHtml(text, sources) {
  let html = escapeHtml(text);
  html = html.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
  html = html.replace(/\[(\d+)\]/g, (match, number) => {
    const index = Number(number);
    if (!Array.isArray(sources) || index < 1 || index > sources.length) {
      return match;
    }
    return `<button type="button" class="cite" data-cite="${index}">[${index}]</button>`;
  });
  return html.replace(/\n/g, "<br>");
}

function renderSourcesHtml(sources) {
  if (!Array.isArray(sources) || sources.length === 0) {
    return "";
  }

  const chips = sources.map((source, index) => {
    const page = source.page_number ? ` · 第${source.page_number}页` : "";
    return `<button type="button" class="source-chip" data-cite="${index + 1}">[${index + 1}] ${escapeHtml(source.document_title)}${page}</button>`;
  }).join("");

  const snippets = sources.map((source, index) => {
    const page = source.page_number ? ` 第${source.page_number}页` : "";
    return `<div class="source-snippet" data-idx="${index + 1}">
      <strong>[${index + 1}] ${escapeHtml(source.document_title)}</strong>${page}
      <div class="meta">${escapeHtml(source.snippet || "")}</div>
    </div>`;
  }).join("");

  return `<div class="sources">${chips}${snippets}</div>`;
}

function renderChatMessages(scrollToBottom = true) {
  const container = document.getElementById("chat-messages");
  if (!container) {
    return;
  }

  if (state.chatMessages.length === 0) {
    container.innerHTML = '<div class="chat-empty">选择知识库，输入问题开始对话。</div>';
    return;
  }

  container.innerHTML = state.chatMessages.map((message) => {
    if (message.role === "user") {
      return `<div class="msg msg-user"><div class="bubble">${escapeHtml(message.content).replace(/\n/g, "<br>")}</div></div>`;
    }
    if (message.pending) {
      return '<div class="msg msg-bot"><div class="bubble pending">正在检索资料并生成回答…</div></div>';
    }
    const sources = Array.isArray(message.sources_json) ? message.sources_json : [];
    return `<div class="msg msg-bot"><div class="bubble">
      <div class="answer">${renderAnswerHtml(message.content, sources)}</div>
      ${renderSourcesHtml(sources)}
      <div class="meta">${message.has_evidence ? "依据检索资料生成" : "没有可用资料"}</div>
    </div></div>`;
  }).join("");

  if (scrollToBottom) {
    container.scrollTop = container.scrollHeight;
  }
}

function sessionScopeLabel(session) {
  const knowledgeBase = state.knowledgeBases.find(
    (item) => item.id === session.knowledge_base_id,
  );
  if (!knowledgeBase) {
    return session.scope_type === "personal" ? "个人知识库" : "企业知识库";
  }
  if (knowledgeBase.scope_type === "personal") {
    return `个人 · ${knowledgeBase.name}`;
  }
  const group = state.groups.find((item) => item.id === knowledgeBase.group_id);
  return `${group ? group.name : "企业"} · ${knowledgeBase.name}`;
}

function renderSessionList() {
  const container = document.getElementById("session-list");
  if (!container) {
    return;
  }

  container.innerHTML = state.chatSessions.length
    ? state.chatSessions.map((session) => `
        <div class="session-item ${session.id === state.currentSessionId ? "active" : ""}" data-session-id="${session.id}" role="button" tabindex="0" aria-current="${session.id === state.currentSessionId ? "true" : "false"}">
          <div class="session-title">${escapeHtml(session.title)}</div>
          <div class="session-scope">${escapeHtml(sessionScopeLabel(session))}</div>
          <div class="meta">${formatTime(session.updated_at)}</div>
          <button type="button" class="session-delete" data-delete-session="${session.id}" title="删除会话" aria-label="删除会话：${escapeHtml(session.title)}">×</button>
        </div>
      `).join("")
    : '<div class="empty">还没有对话</div>';
}

async function loadChatSessions() {
  try {
    state.chatSessions = await apiFetch("/api/chat/sessions");
  } catch (error) {
    state.chatSessions = [];
  }
  renderSessionList();
}

async function loadChatMessages(sessionId) {
  const messages = await apiFetch(`/api/chat/sessions/${sessionId}/messages`);
  state.chatMessages = messages;

  const session = state.chatSessions.find((item) => item.id === sessionId);
  if (session) {
    updateChatScope(session.knowledge_base_id);
  }

  renderChatMessages();
  renderSessionList();
}

function startNewChat() {
  state.currentSessionId = null;
  state.chatMessages = [];
  renderChatMessages();
  renderSessionList();
  const input = document.getElementById("chat-question");
  if (input) {
    input.focus();
  }
}

async function sendChatQuestion(question) {
  if (state.chatSending) {
    return;
  }

  const select = document.getElementById("chat-kb");
  const knowledgeBase = state.knowledgeBases.find(
    (kb) => kb.id === Number(select ? select.value : 0)
  );
  if (!knowledgeBase) {
    showToast("请先选择一个可用的知识库", "error");
    return;
  }

  state.chatSending = true;
  const button = document.getElementById("chat-send");
  if (button) {
    button.disabled = true;
  }

  state.chatMessages.push({ id: `local-user-${Date.now()}`, role: "user", content: question });
  state.chatMessages.push({ id: "local-pending", role: "assistant", pending: true });
  renderChatMessages();

  try {
    const data = await apiFetch(`/api/knowledge-bases/${knowledgeBase.id}/ask`, {
      method: "POST",
      body: JSON.stringify({ question, session_id: state.currentSessionId }),
    });
    state.currentSessionId = data.session_id;
    await loadChatSessions();
    await loadChatMessages(data.session_id);
  } catch (error) {
    state.chatMessages.pop();
    state.chatMessages.push({
      id: `local-error-${Date.now()}`,
      role: "assistant",
      content: `请求失败：${error.message}`,
      sources_json: [],
      has_evidence: false,
    });
    renderChatMessages();
  } finally {
    state.chatSending = false;
    if (button) {
      button.disabled = false;
    }
  }
}

export async function renderChat() {
  setActiveNav("chat");
  const view = document.getElementById("view");
  const params = new URLSearchParams(location.hash.split("?")[1] || "");
  const initialKbId = Number(params.get("kb") || 0);
  const initialQuestion = params.get("q") || "";

  view.innerHTML = `
    <div class="chat-page">
      <aside class="chat-sessions">
        <div class="panel-head">
          <h3>会话</h3>
          <button type="button" class="secondary" id="new-chat">新对话</button>
        </div>
        <div id="session-list" class="session-list"><div class="empty">加载中…</div></div>
      </aside>
      <section class="chat-main">
        <div class="page-head">
          <div><p class="eyebrow">基于授权资料回答</p><h2>知识库问答</h2><p class="muted">答案会附上检索来源；资料不足时会明确说明。</p></div>
          <label class="scope-picker">检索范围<select id="chat-kb" class="kb-select" aria-label="选择问答知识库"></select></label>
        </div>
        <div class="scope-notice" id="chat-scope" aria-live="polite"></div>
        <div id="chat-messages" class="chat-messages" aria-live="polite" aria-relevant="additions text"></div>
        <form id="chat-form" class="chat-input">
          <input id="chat-question" aria-label="输入问题" placeholder="输入问题，Enter 发送" autocomplete="off">
          <button type="submit" class="primary" id="chat-send">发送</button>
        </form>
      </section>
    </div>
  `;

  const kbSelect = document.getElementById("chat-kb");
  kbSelect.innerHTML = state.knowledgeBases.length
    ? state.knowledgeBases.map((kb) => {
      const group = state.groups.find((item) => item.id === kb.group_id);
      const scopeName = kb.scope_type === "personal" ? "个人" : (group ? group.name : "企业");
      return `<option value="${kb.id}">${escapeHtml(scopeName)} · ${escapeHtml(kb.name)}</option>`;
    }).join("")
    : '<option value="">无可用知识库</option>';

  const requestedKb = state.knowledgeBases.find((kb) => kb.id === initialKbId);
  const defaultKb = initialKbId ? requestedKb : state.knowledgeBases[0];
  if (initialKbId && !requestedKb) {
    kbSelect.insertAdjacentHTML("afterbegin", '<option value="">原知识库不可用</option>');
    kbSelect.value = "";
  }
  if (defaultKb) {
    updateChatScope(defaultKb.id);
  } else {
    state.chatKbId = null;
    document.getElementById("chat-scope").textContent = initialKbId
      ? "原检索范围当前不可用，请重新选择一个你有权访问的知识库。"
      : "请先创建或加入知识库，再开始提问。";
    if (initialQuestion) {
      showToast("原检索范围当前不可用，问题未发送", "error");
    }
  }

  document.getElementById("new-chat").addEventListener("click", startNewChat);

  kbSelect.addEventListener("change", () => {
    state.chatKbId = Number(kbSelect.value);
    if (state.currentSessionId) {
      startNewChat();
    }
    updateChatScope(state.chatKbId);
  });

  document.getElementById("chat-form").addEventListener("submit", (event) => {
    event.preventDefault();
    const input = document.getElementById("chat-question");
    const question = input.value.trim();
    if (!question) {
      return;
    }
    input.value = "";
    sendChatQuestion(question);
  });

  document.getElementById("chat-messages").addEventListener("click", (event) => {
    const trigger = event.target.closest(".cite, .source-chip");
    if (!trigger) {
      return;
    }
    const bubble = trigger.closest(".bubble");
    if (!bubble) {
      return;
    }
    const snippet = bubble.querySelector(`.source-snippet[data-idx="${trigger.dataset.cite}"]`);
    if (snippet) {
      snippet.classList.toggle("open");
    }
  });

  document.getElementById("session-list").addEventListener("click", async (event) => {
    const deleteButton = event.target.closest("[data-delete-session]");
    if (deleteButton) {
      const sessionId = Number(deleteButton.dataset.deleteSession);
      if (!(await confirmDialog("确定删除这条会话吗？", "删除"))) {
        return;
      }
      try {
        await apiFetch(`/api/chat/sessions/${sessionId}`, { method: "DELETE" });
        if (state.currentSessionId === sessionId) {
          state.currentSessionId = null;
          state.chatMessages = [];
          renderChatMessages();
        }
        await loadChatSessions();
      } catch (error) {
        showToast(error.message, "error");
      }
      return;
    }

    const item = event.target.closest("[data-session-id]");
    if (!item) {
      return;
    }
    const sessionId = Number(item.dataset.sessionId);
    state.currentSessionId = sessionId;
    try {
      await loadChatMessages(sessionId);
    } catch (error) {
      if (error.status === 404) {
        // 会话已被删除，或知识库权限已被收回：清空当前会话并刷新列表。
        state.currentSessionId = null;
        state.chatMessages = [];
        renderChatMessages();
        await loadChatSessions();
      }
      showToast(error.message, "error");
    }
  });

  document.getElementById("session-list").addEventListener("keydown", (event) => {
    const item = event.target.closest("[data-session-id]");
    if (
      item &&
      !event.target.closest("[data-delete-session]") &&
      (event.key === "Enter" || event.key === " ")
    ) {
      event.preventDefault();
      item.click();
    }
  });

  await loadChatSessions();

  if (initialQuestion && initialKbId && !requestedKb) {
    state.currentSessionId = null;
    state.chatMessages = [];
    renderChatMessages();
  } else if (initialQuestion) {
    state.currentSessionId = null;
    state.chatMessages = [];
    renderChatMessages();
    history.replaceState(null, "", `${location.pathname}#/chat?kb=${defaultKb.id}`);
    await sendChatQuestion(initialQuestion);
  } else if (
    state.currentSessionId &&
    state.chatSessions.some((session) => session.id === state.currentSessionId)
  ) {
    await loadChatMessages(state.currentSessionId);
  } else {
    state.currentSessionId = null;
    state.chatMessages = [];
    renderChatMessages();
  }
}
