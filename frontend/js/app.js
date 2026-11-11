const state = {
  user: null,
  groups: [],
  knowledgeBases: [],
  selectedGroupId: null,
  selectedKbId: null,
};

const ROLE_LABELS = {
  admin: "管理员",
  editor: "编辑者",
  member: "成员",
};

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (char) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  }[char]));
}

function roleLabel(role) {
  return ROLE_LABELS[role] || role;
}

function setActiveNav(name) {
  document.querySelectorAll("[data-nav]").forEach((link) => {
    link.classList.toggle("active", link.dataset.nav === name);
  });
}

function canEditKnowledgeBase(knowledgeBase) {
  if (!knowledgeBase) {
    return false;
  }
  if (knowledgeBase.scope_type === "personal") {
    return true;
  }
  const group = state.groups.find((item) => item.id === knowledgeBase.group_id);
  return Boolean(group) && ["editor", "admin"].includes(group.role);
}

async function init() {
  requireLogin();

  try {
    const [user, groups, knowledgeBases] = await Promise.all([
      apiFetch("/api/auth/me"),
      apiFetch("/api/groups"),
      apiFetch("/api/knowledge-bases"),
    ]);
    state.user = user;
    state.groups = groups;
    state.knowledgeBases = knowledgeBases;
    document.getElementById("current-user").textContent = user.username;
  } catch (error) {
    document.getElementById("view").innerHTML = `<div class="empty">${escapeHtml(error.message)}</div>`;
    return;
  }

  document.getElementById("logout").addEventListener("click", () => {
    localStorage.removeItem("token");
    location.href = "/login.html";
  });

  window.addEventListener("hashchange", route);
  route();
}

function route() {
  const path = (location.hash || "#/enterprise").slice(1).split("?")[0];
  if (path === "/personal") {
    renderPersonal();
  } else if (path === "/chat") {
    renderChat();
  } else {
    renderEnterprise();
  }
}

function renderEnterprise() {
  setActiveNav("enterprise");
  const view = document.getElementById("view");

  if (state.groups.length === 0) {
    view.innerHTML = `
      <div class="page-head"><h2>企业知识库</h2></div>
      <div class="panel"><div class="empty">你还没有加入任何企业群组，请联系管理员添加。</div></div>
    `;
    return;
  }

  if (!state.groups.some((group) => group.id === state.selectedGroupId)) {
    state.selectedGroupId = state.groups[0].id;
  }
  const group = state.groups.find((item) => item.id === state.selectedGroupId);
  const groupBases = state.knowledgeBases.filter(
    (kb) => kb.scope_type === "enterprise_group" && kb.group_id === group.id
  );
  const selectedKb = groupBases.find((kb) => kb.id === state.selectedKbId) || groupBases[0] || null;
  state.selectedKbId = selectedKb ? selectedKb.id : null;

  view.innerHTML = `
    <div class="page-head">
      <h2>企业知识库</h2>
      <div class="search-bar">
        <input id="ai-question" placeholder="在当前知识库中提问…">
        <button class="primary" id="ai-search">AI 搜索</button>
      </div>
    </div>

    <div class="panel">
      <h3>我的群组</h3>
      <div class="card-list">
        ${state.groups.map((item) => `
          <div class="card ${item.id === group.id ? "selected" : ""}" data-group-id="${item.id}">
            <div class="title">${escapeHtml(item.name)}<span class="tag">${roleLabel(item.role)}</span></div>
            <div class="meta">${escapeHtml(item.group_type)}${item.description ? " · " + escapeHtml(item.description) : ""}</div>
          </div>
        `).join("")}
      </div>
    </div>

    <div class="panel">
      <h3>${escapeHtml(group.name)} 的知识库</h3>
      <div class="card-list">
        ${groupBases.length ? groupBases.map((kb) => `
          <div class="card ${kb.id === state.selectedKbId ? "selected" : ""}" data-kb-id="${kb.id}">
            <div class="title">${escapeHtml(kb.name)}</div>
            <div class="meta">企业知识库 · 创建于 ${kb.created_at.slice(0, 10)}</div>
          </div>
        `).join("") : '<div class="empty">该群组还没有知识库</div>'}
      </div>
    </div>

    <div class="panel" id="doc-panel"><div class="empty">文档加载中…</div></div>
  `;

  view.querySelectorAll("[data-group-id]").forEach((card) => {
    card.addEventListener("click", () => {
      state.selectedGroupId = Number(card.dataset.groupId);
      state.selectedKbId = null;
      renderEnterprise();
    });
  });

  view.querySelectorAll("[data-kb-id]").forEach((card) => {
    card.addEventListener("click", () => {
      state.selectedKbId = Number(card.dataset.kbId);
      renderEnterprise();
    });
  });

  document.getElementById("ai-search").addEventListener("click", () => {
    const question = document.getElementById("ai-question").value.trim();
    const knowledgeBase = groupBases.find((kb) => kb.id === state.selectedKbId) || groupBases[0];
    if (!question) {
      alert("请输入问题");
      return;
    }
    if (!knowledgeBase) {
      alert("该群组还没有知识库，无法搜索");
      return;
    }
    location.hash = `#/chat?kb=${knowledgeBase.id}&q=${encodeURIComponent(question)}`;
  });

  if (selectedKb) {
    loadDocuments(selectedKb);
  } else {
    document.getElementById("doc-panel").innerHTML = '<div class="empty">该群组还没有知识库</div>';
  }
}

function renderPersonal() {
  setActiveNav("personal");
  const view = document.getElementById("view");
  const personalBases = state.knowledgeBases.filter((kb) => kb.scope_type === "personal");
  const selectedKb = personalBases.find((kb) => kb.id === state.selectedKbId) || personalBases[0] || null;
  state.selectedKbId = selectedKb ? selectedKb.id : null;

  view.innerHTML = `
    <div class="page-head">
      <h2>个人知识库</h2>
      <div class="search-bar">
        <input id="ai-question" placeholder="在我的知识库中提问…">
        <button class="primary" id="ai-search">AI 搜索</button>
      </div>
    </div>

    <div class="panel">
      <h3>我的知识库</h3>
      <div class="card-list">
        ${personalBases.length ? personalBases.map((kb) => `
          <div class="card ${kb.id === state.selectedKbId ? "selected" : ""}" data-kb-id="${kb.id}">
            <div class="title">${escapeHtml(kb.name)}</div>
            <div class="meta">个人知识库 · 仅自己可见 · 创建于 ${kb.created_at.slice(0, 10)}</div>
          </div>
        `).join("") : '<div class="empty">你还没有个人知识库</div>'}
      </div>
    </div>

    <div class="panel" id="doc-panel"><div class="empty">文档加载中…</div></div>
  `;

  view.querySelectorAll("[data-kb-id]").forEach((card) => {
    card.addEventListener("click", () => {
      state.selectedKbId = Number(card.dataset.kbId);
      renderPersonal();
    });
  });

  document.getElementById("ai-search").addEventListener("click", () => {
    const question = document.getElementById("ai-question").value.trim();
    const knowledgeBase = personalBases.find((kb) => kb.id === state.selectedKbId) || personalBases[0];
    if (!question) {
      alert("请输入问题");
      return;
    }
    if (!knowledgeBase) {
      alert("你还没有个人知识库，无法搜索");
      return;
    }
    location.hash = `#/chat?kb=${knowledgeBase.id}&q=${encodeURIComponent(question)}`;
  });

  if (selectedKb) {
    loadDocuments(selectedKb);
  } else {
    document.getElementById("doc-panel").innerHTML = '<div class="empty">你还没有个人知识库</div>';
  }
}

async function loadDocuments(knowledgeBase) {
  const panel = document.getElementById("doc-panel");
  if (!panel) {
    return;
  }
  const editable = canEditKnowledgeBase(knowledgeBase);
  panel.innerHTML = '<div class="empty">文档加载中…</div>';

  try {
    const documents = await apiFetch(`/api/knowledge-bases/${knowledgeBase.id}/documents`);
    const listHtml = documents.length
      ? documents.map((doc) => `
          <div class="card" data-doc-id="${doc.id}">
            <div class="title">${escapeHtml(doc.title)}<span class="tag">${escapeHtml(doc.status)}</span></div>
            <div class="meta">${escapeHtml(doc.file_type)} · 更新于 ${escapeHtml(doc.updated_at.replace("T", " ").slice(0, 16))}</div>
          </div>
        `).join("")
      : '<div class="empty">这个知识库还没有文档</div>';

    panel.innerHTML = `
      <div class="panel-head">
        <h3>${escapeHtml(knowledgeBase.name)} 的文档</h3>
        ${editable ? `
          <div class="actions">
            <button class="secondary" id="upload-doc">上传 PDF/TXT</button>
            <button class="primary" id="new-doc">新建文档</button>
            <input type="file" id="upload-input" accept=".pdf,.txt" hidden>
          </div>
        ` : ""}
      </div>
      <div class="card-list">${listHtml}</div>
    `;

    if (editable) {
      const uploadInput = panel.querySelector("#upload-input");
      panel.querySelector("#upload-doc").addEventListener("click", () => uploadInput.click());
      uploadInput.addEventListener("change", async () => {
        const file = uploadInput.files[0];
        if (!file) {
          return;
        }
        const form = new FormData();
        form.append("file", file);
        try {
          await apiFetch(`/api/knowledge-bases/${knowledgeBase.id}/documents/upload`, {
            method: "POST",
            body: form,
          });
          loadDocuments(knowledgeBase);
        } catch (error) {
          alert(error.message);
        }
      });

      document.getElementById("new-doc").addEventListener("click", () => {
        openDocumentEditor(knowledgeBase, null);
      });
    }

    panel.querySelectorAll("[data-doc-id]").forEach((card) => {
      card.addEventListener("click", async () => {
        try {
          const documentData = await apiFetch(`/api/documents/${card.dataset.docId}`);
          openDocumentEditor(knowledgeBase, documentData);
        } catch (error) {
          alert(error.message);
        }
      });
    });
  } catch (error) {
    panel.innerHTML = `<div class="empty">${escapeHtml(error.message)}</div>`;
  }
}

function openDocumentEditor(knowledgeBase, documentData) {
  const editable = canEditKnowledgeBase(knowledgeBase);
  const isNew = documentData === null;

  const overlay = document.createElement("div");
  overlay.className = "modal-overlay";
  overlay.innerHTML = `
    <div class="modal">
      <h3>${isNew ? "新建文档" : editable ? "编辑文档" : "查看文档"}</h3>
      <label>
        标题
        <input id="doc-title" maxlength="255" ${editable ? "" : "readonly"}>
      </label>
      <label>
        正文（Markdown / 纯文本）
        <textarea id="doc-content" rows="12" ${editable ? "" : "readonly"}></textarea>
      </label>
      <p id="doc-error" class="error" hidden></p>
      <div class="modal-actions">
        ${documentData && editable ? '<button class="danger" id="doc-delete">删除</button>' : ""}
        <span class="spacer"></span>
        <button class="link" id="doc-close">关闭</button>
        ${editable ? '<button class="primary" id="doc-save">保存</button>' : ""}
      </div>
    </div>
  `;
  document.body.appendChild(overlay);

  const titleInput = overlay.querySelector("#doc-title");
  const contentInput = overlay.querySelector("#doc-content");
  const errorBox = overlay.querySelector("#doc-error");
  titleInput.value = documentData ? documentData.title : "";
  contentInput.value = documentData ? documentData.content || "" : "";
  titleInput.focus();

  const close = () => overlay.remove();
  overlay.addEventListener("click", (event) => {
    if (event.target === overlay) {
      close();
    }
  });
  overlay.querySelector("#doc-close").addEventListener("click", close);

  if (editable) {
    overlay.querySelector("#doc-save").addEventListener("click", async () => {
      errorBox.hidden = true;
      const payload = {
        title: titleInput.value.trim(),
        content: contentInput.value,
      };
      if (!payload.title) {
        errorBox.textContent = "标题不能为空";
        errorBox.hidden = false;
        return;
      }
      try {
        if (isNew) {
          await apiFetch(`/api/knowledge-bases/${knowledgeBase.id}/documents`, {
            method: "POST",
            body: JSON.stringify(payload),
          });
        } else {
          await apiFetch(`/api/documents/${documentData.id}`, {
            method: "PUT",
            body: JSON.stringify(payload),
          });
        }
        close();
        loadDocuments(knowledgeBase);
      } catch (error) {
        errorBox.textContent = error.message;
        errorBox.hidden = false;
      }
    });

    if (documentData) {
      overlay.querySelector("#doc-delete").addEventListener("click", async () => {
        if (!confirm(`确定删除《${documentData.title}》吗？`)) {
          return;
        }
        try {
          await apiFetch(`/api/documents/${documentData.id}`, { method: "DELETE" });
          close();
          loadDocuments(knowledgeBase);
        } catch (error) {
          errorBox.textContent = error.message;
          errorBox.hidden = false;
        }
      });
    }
  }
}

function renderChat() {
  setActiveNav("chat");
  const view = document.getElementById("view");
  const params = new URLSearchParams((location.hash.split("?")[1] || ""));
  const question = params.get("q") || "";
  const knowledgeBaseId = Number(params.get("kb") || 0);
  const knowledgeBase = state.knowledgeBases.find((kb) => kb.id === knowledgeBaseId);

  view.innerHTML = `
    <div class="page-head"><h2>智能体问答</h2></div>

    <div class="panel">
      <h3>检索范围</h3>
      <div class="card">
        <div class="title">${knowledgeBase ? escapeHtml(knowledgeBase.name) : "未指定（请从知识库页面发起提问）"}</div>
        <div class="meta">你的问题：${question ? escapeHtml(question) : "暂无问题"}</div>
      </div>
    </div>

    <div class="panel">
      <h3>检索到的片段</h3>
      <div id="search-results"><div class="empty">检索中…</div></div>
    </div>

    <div class="panel">
      <div class="panel-head">
        <h3>AI 回答</h3>
        ${knowledgeBase && question ? '<button class="primary" id="ask-button">生成回答</button>' : ""}
      </div>
      <div id="ask-answer"><div class="empty">点击“生成回答”，系统会把检索到的片段交给大模型。</div></div>
    </div>
  `;

  if (knowledgeBase && question) {
    loadSearchResults(knowledgeBase, question);
    document.getElementById("ask-button").addEventListener("click", () => {
      askQuestion(knowledgeBase, question);
    });
  } else {
    document.getElementById("search-results").innerHTML =
      '<div class="empty">请从企业知识库或个人知识库页面输入问题并发起搜索。</div>';
  }
}

async function askQuestion(knowledgeBase, question) {
  const container = document.getElementById("ask-answer");
  const button = document.getElementById("ask-button");
  if (!container) {
    return;
  }

  if (button) {
    button.disabled = true;
    button.textContent = "生成中…";
  }
  container.innerHTML = '<div class="empty">大模型生成中，请稍候…</div>';

  try {
    const data = await apiFetch(`/api/knowledge-bases/${knowledgeBase.id}/ask`, {
      method: "POST",
      body: JSON.stringify({ question }),
    });

    const sourcesHtml = data.sources.length
      ? `<div class="meta">来源：${data.sources.map((source) => {
          const location = source.page_number ? ` 第${source.page_number}页` : "";
          return `${escapeHtml(source.document_title)}${location}`;
        }).join("；")}</div>`
      : "";

    container.innerHTML = `
      <div class="card">
        <div class="title">${escapeHtml(data.answer)}</div>
        ${sourcesHtml}
        <div class="meta">${data.has_evidence ? "依据检索资料生成" : "没有可用资料"}</div>
      </div>
    `;
  } catch (error) {
    container.innerHTML = `<div class="empty">${escapeHtml(error.message)}</div>`;
  } finally {
    if (button) {
      button.disabled = false;
      button.textContent = "生成回答";
    }
  }
}

async function loadSearchResults(knowledgeBase, question) {
  const container = document.getElementById("search-results");
  if (!container) {
    return;
  }

  try {
    const data = await apiFetch(`/api/knowledge-bases/${knowledgeBase.id}/search`, {
      method: "POST",
      body: JSON.stringify({ question }),
    });

    if (!data.matches.length) {
      container.innerHTML = '<div class="empty">没有检索到相关片段</div>';
      return;
    }

    container.innerHTML = data.matches.map((match) => `
      <div class="card">
        <div class="title">
          ${escapeHtml(match.document_title)}
          <span class="tag">${match.page_number ? `第 ${match.page_number} 页` : `片段 ${match.chunk_index + 1}`}</span>
          <span class="tag">相似度 ${(match.score * 100).toFixed(1)}%</span>
        </div>
        <div class="meta">${escapeHtml(match.content)}</div>
      </div>
    `).join("");
  } catch (error) {
    container.innerHTML = `<div class="empty">${escapeHtml(error.message)}</div>`;
  }
}

init();
