const state = {
  user: null,
  groups: [],
  knowledgeBases: [],
  selectedGroupId: null,
  selectedKbId: null,
  chatSessions: [],
  chatMessages: [],
  currentSessionId: null,
  chatKbId: null,
  chatSending: false,
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

function showToast(message, tone = "info") {
  let toast = document.getElementById("app-toast");
  if (!toast) {
    toast = document.createElement("div");
    toast.id = "app-toast";
    toast.className = "toast";
    toast.setAttribute("role", "status");
    toast.setAttribute("aria-live", "polite");
    document.body.appendChild(toast);
  }
  toast.dataset.tone = tone;
  toast.textContent = message;
  toast.classList.add("show");
  window.clearTimeout(showToast.timeout);
  showToast.timeout = window.setTimeout(() => toast.classList.remove("show"), 2800);
}

function documentStatus(status) {
  const values = {
    READY: ["已就绪", "ready"],
    PROCESSING: ["处理中", "processing"],
    FAILED: ["处理失败", "failed"],
    UPLOADED: ["待处理", "processing"],
  };
  return values[status] || [status || "未知状态", "processing"];
}

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
      <div class="page-head"><div><p class="eyebrow">共享知识空间</p><h2>企业知识库</h2><p class="muted">按群组查阅文档，并在授权范围内提问。</p></div></div>
      <div class="panel">
        <div class="panel-head">
          <h3>我的群组</h3>
          <button type="button" class="secondary" id="new-group">新建群组</button>
        </div>
        <div class="empty">你还没有加入任何企业群组，可以新建一个，或等待管理员添加。</div>
      </div>
    `;
    document.getElementById("new-group").addEventListener("click", openCreateGroupModal);
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
      <div><p class="eyebrow">共享知识空间</p><h2>企业知识库</h2><p class="muted">选择群组和知识库后，可查看文档或直接提问。</p></div>
      <form class="search-bar" id="ai-search-form">
        <input id="ai-question" aria-label="在当前知识库中提问" placeholder="搜索文档内容，或直接提问…" autocomplete="off">
        <button class="primary" id="ai-search" type="submit">提问</button>
      </form>
    </div>

    <div class="scope-notice"><span aria-hidden="true">◈</span><span>当前检索范围：</span><strong>${escapeHtml(group.name)}${selectedKb ? ` · ${escapeHtml(selectedKb.name)}` : ""}</strong><span>仅包含你有权访问的资料</span></div>

    <div class="panel">
      <div class="panel-head">
        <h3>我的群组</h3>
        <button type="button" class="secondary" id="new-group">新建群组</button>
      </div>
      <div class="card-list">
        ${state.groups.map((item) => `
          <div class="card ${item.id === group.id ? "selected" : ""}" data-group-id="${item.id}" role="button" tabindex="0" aria-pressed="${item.id === group.id}">
            <div class="title">${escapeHtml(item.name)}<span class="tag">${roleLabel(item.role)}</span></div>
            <div class="meta">${escapeHtml(item.group_type)}${item.description ? " · " + escapeHtml(item.description) : ""}</div>
          </div>
        `).join("")}
      </div>
    </div>

    <div class="panel">
      <div class="panel-head">
        <h3>${escapeHtml(group.name)} 的知识库</h3>
        <div class="actions">
          ${["editor", "admin"].includes(group.role) ? '<button type="button" class="secondary" id="new-kb">新建知识库</button>' : ""}
          ${group.role === "admin" ? '<button type="button" class="secondary" id="manage-members">成员管理</button>' : ""}
        </div>
      </div>
      <div class="card-list">
        ${groupBases.length ? groupBases.map((kb) => `
          <div class="card ${kb.id === state.selectedKbId ? "selected" : ""}" data-kb-id="${kb.id}" role="button" tabindex="0" aria-pressed="${kb.id === state.selectedKbId}">
            <div class="title">${escapeHtml(kb.name)}</div>
            <div class="meta">企业知识库 · 创建于 ${kb.created_at.slice(0, 10)}</div>
          </div>
        `).join("") : '<div class="empty">该群组还没有知识库</div>'}
      </div>
    </div>

    <div class="panel" id="doc-panel"><div class="empty">文档加载中…</div></div>
  `;

  view.querySelectorAll("[data-group-id]").forEach((card) => {
    const selectGroup = () => {
      state.selectedGroupId = Number(card.dataset.groupId);
      state.selectedKbId = null;
      renderEnterprise();
    };
    card.addEventListener("click", selectGroup);
    card.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        selectGroup();
      }
    });
  });

  view.querySelectorAll("[data-kb-id]").forEach((card) => {
    const selectKnowledgeBase = () => {
      state.selectedKbId = Number(card.dataset.kbId);
      renderEnterprise();
    };
    card.addEventListener("click", selectKnowledgeBase);
    card.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        selectKnowledgeBase();
      }
    });
  });

  document.getElementById("ai-search-form").addEventListener("submit", (event) => {
    event.preventDefault();
    const question = document.getElementById("ai-question").value.trim();
    const knowledgeBase = groupBases.find((kb) => kb.id === state.selectedKbId) || groupBases[0];
    if (!question) {
      showToast("请输入问题后再提问", "error");
      return;
    }
    if (!knowledgeBase) {
      showToast("该群组还没有知识库，暂时无法提问", "error");
      return;
    }
    location.hash = `#/chat?kb=${knowledgeBase.id}&q=${encodeURIComponent(question)}`;
  });

  document.getElementById("new-group").addEventListener("click", openCreateGroupModal);

  const newKbButton = document.getElementById("new-kb");
  if (newKbButton) {
    newKbButton.addEventListener("click", () => openCreateKnowledgeBaseModal(group));
  }

  const membersButton = document.getElementById("manage-members");
  if (membersButton) {
    membersButton.addEventListener("click", () => {
      openMembersModal(group, async () => {
        await refreshWorkspace();
        renderEnterprise();
      });
    });
  }

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
      <div><p class="eyebrow">私人知识空间</p><h2>个人知识库</h2><p class="muted">整理个人文档，并只在自己的资料中搜索和提问。</p></div>
      <form class="search-bar" id="ai-search-form">
        <input id="ai-question" aria-label="在个人知识库中提问" placeholder="搜索我的文档，或直接提问…" autocomplete="off">
        <button class="primary" id="ai-search" type="submit">提问</button>
      </form>
    </div>

    <div class="scope-notice"><span aria-hidden="true">◈</span><span>当前检索范围：</span><strong>${selectedKb ? escapeHtml(selectedKb.name) : "个人知识库"}</strong><span>仅自己可见</span></div>

    <div class="panel">
      <div class="panel-head">
        <h3>我的知识库</h3>
        ${personalBases.length === 0 ? '<button type="button" class="secondary" id="new-personal-kb">新建个人知识库</button>' : ""}
      </div>
      <div class="card-list">
        ${personalBases.length ? personalBases.map((kb) => `
          <div class="card ${kb.id === state.selectedKbId ? "selected" : ""}" data-kb-id="${kb.id}" role="button" tabindex="0" aria-pressed="${kb.id === state.selectedKbId}">
            <div class="title">${escapeHtml(kb.name)}</div>
            <div class="meta">个人知识库 · 仅自己可见 · 创建于 ${kb.created_at.slice(0, 10)}</div>
          </div>
        `).join("") : '<div class="empty">你还没有个人知识库</div>'}
      </div>
    </div>

    <div class="panel" id="doc-panel"><div class="empty">文档加载中…</div></div>
  `;

  view.querySelectorAll("[data-kb-id]").forEach((card) => {
    const selectKnowledgeBase = () => {
      state.selectedKbId = Number(card.dataset.kbId);
      renderPersonal();
    };
    card.addEventListener("click", selectKnowledgeBase);
    card.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        selectKnowledgeBase();
      }
    });
  });

  document.getElementById("ai-search-form").addEventListener("submit", (event) => {
    event.preventDefault();
    const question = document.getElementById("ai-question").value.trim();
    const knowledgeBase = personalBases.find((kb) => kb.id === state.selectedKbId) || personalBases[0];
    if (!question) {
      showToast("请输入问题后再提问", "error");
      return;
    }
    if (!knowledgeBase) {
      showToast("请先创建个人知识库，再开始提问", "error");
      return;
    }
    location.hash = `#/chat?kb=${knowledgeBase.id}&q=${encodeURIComponent(question)}`;
  });

  const newPersonalKbButton = document.getElementById("new-personal-kb");
  if (newPersonalKbButton) {
    newPersonalKbButton.addEventListener("click", openCreatePersonalKbModal);
  }

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
      ? documents.map((doc) => {
          const [statusText, statusClass] = documentStatus(doc.status);
          const fileType = String(doc.file_type || "").toUpperCase();
          return `
          <div class="card document-card" data-doc-id="${doc.id}" role="button" tabindex="0" aria-label="打开文档：${escapeHtml(doc.title)}">
            <div class="doc-row">
              <span class="file-icon ${fileType === "MARKDOWN" ? "md" : ""}" aria-hidden="true">${escapeHtml(fileType.slice(0, 4))}</span>
              <div class="doc-copy"><div class="title">${escapeHtml(doc.title)}</div><div class="meta">更新于 ${escapeHtml(doc.updated_at.replace("T", " ").slice(0, 16))}</div></div>
              <span class="doc-status ${statusClass}"><i class="status-dot"></i>${escapeHtml(statusText)}</span>
              ${editable && doc.status === "FAILED" ? `<button type="button" class="secondary btn-sm" data-reindex-id="${doc.id}">重建索引</button>` : ""}
            </div>
          </div>
        `;
        }).join("")
      : '<div class="empty">这个知识库还没有文档</div>';

    panel.innerHTML = `
      <div class="panel-head">
        <h3>${escapeHtml(knowledgeBase.name)} 的文档</h3>
        ${editable ? `
          <div class="actions">
            <button type="button" class="secondary" id="upload-doc">上传 PDF/TXT</button>
            <button type="button" class="primary" id="new-doc">新建文档</button>
            <input type="file" id="upload-input" accept=".pdf,.txt" hidden>
          </div>
        ` : ""}
      </div>
      <div class="card-list">${listHtml}</div>
    `;

    if (editable) {
      const uploadInput = panel.querySelector("#upload-input");
      const uploadButton = panel.querySelector("#upload-doc");
      uploadButton.addEventListener("click", () => uploadInput.click());
      uploadInput.addEventListener("change", async () => {
        const file = uploadInput.files[0];
        if (!file) {
          return;
        }
        const form = new FormData();
        form.append("file", file);
        uploadButton.disabled = true;
        uploadButton.textContent = "解析中…";
        showToast("文件已上传，正在解析并建立索引，请稍候…", "info");
        try {
          const uploaded = await apiFetch(`/api/knowledge-bases/${knowledgeBase.id}/documents/upload`, {
            method: "POST",
            body: form,
          });
          showToast(
            uploaded.status === "FAILED" ? "文档已上传，但解析失败；打开文档查看原因" : "文档已上传并完成处理",
            uploaded.status === "FAILED" ? "error" : "success",
          );
          await loadDocuments(knowledgeBase);
        } catch (error) {
          showToast(error.message, "error");
        } finally {
          uploadInput.value = "";
          uploadButton.disabled = false;
          uploadButton.textContent = "上传 PDF/TXT";
        }
      });

      document.getElementById("new-doc").addEventListener("click", () => {
        openDocumentEditor(knowledgeBase, null);
      });
    }

    panel.querySelectorAll("[data-doc-id]").forEach((card) => {
      const openDocument = async () => {
        try {
          const documentData = await apiFetch(`/api/documents/${card.dataset.docId}`);
          openDocumentEditor(knowledgeBase, documentData);
        } catch (error) {
          showToast(error.message, "error");
        }
      };
      card.addEventListener("click", openDocument);
      card.addEventListener("keydown", (event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          openDocument();
        }
      });
    });

    panel.querySelectorAll("[data-reindex-id]").forEach((button) => {
      button.addEventListener("click", async (event) => {
        event.stopPropagation();
        button.disabled = true;
        button.textContent = "处理中…";
        try {
          const result = await apiFetch(`/api/documents/${button.dataset.reindexId}/reindex`, {
            method: "POST",
          });
          showToast(
            result.status === "READY" ? "索引已重建" : "重建失败，请打开文档查看原因",
            result.status === "READY" ? "success" : "error",
          );
          await loadDocuments(knowledgeBase);
        } catch (error) {
          button.disabled = false;
          button.textContent = "重建索引";
          showToast(error.message, "error");
        }
      });
    });
  } catch (error) {
    panel.innerHTML = `<div class="empty">${escapeHtml(error.message)}</div>`;
  }
}

async function fetchDocumentBlob(documentId) {
  const response = await fetch(`/api/documents/${documentId}/download`, {
    headers: { Authorization: `Bearer ${getToken()}` },
  });
  if (!response.ok) {
    let detail = `${response.status} ${response.statusText}`;
    try {
      const body = await response.json();
      if (body.detail) {
        detail = body.detail;
      }
    } catch (error) {
      // 保留状态码信息
    }
    throw new Error(detail);
  }
  return response.blob();
}

function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename || "download";
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

function renderMarkdownPreview(text) {
  let html = escapeHtml(text);
  html = html.replace(/^### (.+)$/gm, "<h4>$1</h4>");
  html = html.replace(/^## (.+)$/gm, "<h3>$1</h3>");
  html = html.replace(/^# (.+)$/gm, "<h2>$1</h2>");
  html = html.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
  html = html.replace(/^- (.+)$/gm, "• $1");
  return html.replace(/\n/g, "<br>");
}

function documentErrorInfo(message) {
  const text = String(message || "");
  if (text.includes("重建索引失败，已保留旧索引")) {
    return { summary: "最近一次重建索引失败，当前仍在使用旧索引。", detail: text };
  }
  if (text.includes("没有可索引的文本内容")) {
    return { summary: "文档里没有可用文字，可能是扫描件或空文件。", detail: text };
  }
  if (text.includes("超过 10MB")) {
    return { summary: "文件超过 10MB 限制。", detail: text };
  }
  if (/pdf/i.test(text) && /(无法|失败|损坏|open|corrupt|encrypted|invalid)/i.test(text)) {
    return { summary: "PDF 文件损坏或无法解析。", detail: text };
  }
  return { summary: text.split("\n")[0].slice(0, 80) || "处理失败", detail: text };
}

function renderDocumentError(errorBox, documentData) {
  if (!documentData || !documentData.error_message) {
    errorBox.hidden = true;
    return;
  }
  const { summary, detail } = documentErrorInfo(documentData.error_message);
  const failed = documentData.status === "FAILED";
  errorBox.classList.add("inline-feedback");
  if (!failed) {
    errorBox.classList.add("warn");
  }
  errorBox.innerHTML = `
    <div>${failed ? "处理失败" : "提示"}：${escapeHtml(summary)}</div>
    <details><summary>技术详情</summary><pre>${escapeHtml(detail)}</pre></details>
  `;
  errorBox.hidden = false;
}

function openUploadedViewer(overlay, knowledgeBase, documentData, editable) {
  overlay.innerHTML = `
    <div class="modal modal-wide">
      <h3>${escapeHtml(documentData.title)}</h3>
      <div class="meta">${escapeHtml((documentData.file_type || "").toUpperCase())} · ${documentData.file_size || 0} 字节</div>
      <div id="doc-preview" class="doc-preview"><div class="empty">加载预览中…</div></div>
      <p id="doc-error" class="error" hidden></p>
      <div class="modal-actions">
        ${editable ? '<button class="danger" id="doc-delete">删除</button>' : ""}
        <span class="spacer"></span>
        <button type="button" class="secondary" id="doc-download">下载原文件</button>
        <button type="button" class="link" id="doc-close">关闭</button>
      </div>
    </div>
  `;

  const container = overlay.querySelector("#doc-preview");
  const errorBox = overlay.querySelector("#doc-error");
  renderDocumentError(errorBox, documentData);
  const downloadButton = overlay.querySelector("#doc-download");
  let objectUrl = null;

  const close = () => {
    if (objectUrl) {
      URL.revokeObjectURL(objectUrl);
    }
    overlay.remove();
  };

  overlay.addEventListener("click", (event) => {
    if (event.target === overlay) {
      close();
    }
  });
  overlay.querySelector("#doc-close").addEventListener("click", close);

  if (editable) {
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

  (async () => {
    try {
      const blob = await fetchDocumentBlob(documentData.id);
      downloadButton.addEventListener("click", () => {
        downloadBlob(blob, documentData.original_filename || documentData.title);
      });

      if (documentData.file_type === "pdf") {
        objectUrl = URL.createObjectURL(blob);
        container.innerHTML = `<embed class="pdf-embed" type="application/pdf" src="${objectUrl}">`;
      } else {
        const text = await blob.text();
        const pre = document.createElement("pre");
        pre.className = "doc-text";
        pre.textContent = text;
        container.innerHTML = "";
        container.appendChild(pre);
      }
    } catch (error) {
      container.innerHTML = `<div class="empty">${escapeHtml(error.message)}</div>`;
    }
  })();
}

function openTextEditor(overlay, knowledgeBase, documentData, editable, isNew) {
  overlay.innerHTML = `
    <div class="modal">
      <h3>${isNew ? "新建文档" : editable ? "编辑文档" : "查看文档"}</h3>
      <label>
        标题
        <input id="doc-title" maxlength="255" ${editable ? "" : "readonly"}>
      </label>
      <div class="panel-head doc-mode">
        <span class="meta">正文（Markdown / 纯文本）</span>
        <button type="button" class="link" id="doc-toggle-preview">预览</button>
      </div>
      <textarea id="doc-content" rows="12" ${editable ? "" : "readonly"}></textarea>
      <div id="doc-preview" class="doc-preview" hidden></div>
      <p id="doc-error" class="error" hidden></p>
      <div class="modal-actions">
        ${documentData && editable ? '<button class="danger" id="doc-delete">删除</button>' : ""}
        <span class="spacer"></span>
        <button type="button" class="link" id="doc-close">关闭</button>
        ${editable ? '<button type="button" class="primary" id="doc-save">保存</button>' : ""}
      </div>
    </div>
  `;

  const titleInput = overlay.querySelector("#doc-title");
  const contentInput = overlay.querySelector("#doc-content");
  const previewBox = overlay.querySelector("#doc-preview");
  const togglePreview = overlay.querySelector("#doc-toggle-preview");
  const errorBox = overlay.querySelector("#doc-error");

  if (documentData) {
    renderDocumentError(errorBox, documentData);
  }

  titleInput.value = documentData ? documentData.title : "";
  contentInput.value = documentData ? documentData.content || "" : "";
  titleInput.focus();

  let previewing = false;
  togglePreview.addEventListener("click", () => {
    previewing = !previewing;
    if (previewing) {
      previewBox.innerHTML = renderMarkdownPreview(contentInput.value);
      previewBox.hidden = false;
      contentInput.hidden = true;
      togglePreview.textContent = "编辑";
    } else {
      previewBox.hidden = true;
      contentInput.hidden = false;
      togglePreview.textContent = "预览";
    }
  });

  const close = () => overlay.remove();
  overlay.addEventListener("click", (event) => {
    if (event.target === overlay) {
      close();
    }
  });
  overlay.querySelector("#doc-close").addEventListener("click", close);

  if (!editable) {
    return;
  }

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

function openDocumentEditor(knowledgeBase, documentData) {
  const editable = canEditKnowledgeBase(knowledgeBase);
  const isNew = documentData === null;
  const isUploaded = Boolean(documentData && documentData.file_path);

  const overlay = document.createElement("div");
  overlay.className = "modal-overlay";
  document.body.appendChild(overlay);

  if (isUploaded) {
    openUploadedViewer(overlay, knowledgeBase, documentData, editable);
  } else {
    openTextEditor(overlay, knowledgeBase, documentData, editable, isNew);
  }
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

async function renderChat() {
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
      if (!confirm("确定删除这条会话吗？")) {
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
    state.currentSessionId = Number(item.dataset.sessionId);
    try {
      await loadChatMessages(state.currentSessionId);
    } catch (error) {
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

async function refreshWorkspace() {
  const [groups, knowledgeBases] = await Promise.all([
    apiFetch("/api/groups"),
    apiFetch("/api/knowledge-bases"),
  ]);
  state.groups = groups;
  state.knowledgeBases = knowledgeBases;
}

function openModal(innerHtml, onReady) {
  const overlay = document.createElement("div");
  overlay.className = "modal-overlay";
  overlay.innerHTML = `<div class="modal">${innerHtml}</div>`;
  document.body.appendChild(overlay);

  const close = () => overlay.remove();
  overlay.addEventListener("click", (event) => {
    if (event.target === overlay) {
      close();
    }
  });

  onReady(overlay, close);
}

function openCreateGroupModal() {
  openModal(`
    <h3>新建群组</h3>
    <label>群组名称<input id="group-name" maxlength="100" placeholder="例如：研发部"></label>
    <label>类型
      <select id="group-type">
        <option value="department">部门</option>
        <option value="project">项目</option>
        <option value="company">公司</option>
      </select>
    </label>
    <label>说明（可选）<input id="group-desc" maxlength="500"></label>
    <p class="error" id="form-error" hidden></p>
    <div class="modal-actions">
      <span class="spacer"></span>
      <button type="button" class="link" id="form-cancel">取消</button>
      <button type="button" class="primary" id="form-submit">创建</button>
    </div>
  `, (overlay, close) => {
    const errorBox = overlay.querySelector("#form-error");

    overlay.querySelector("#form-cancel").addEventListener("click", close);
    overlay.querySelector("#form-submit").addEventListener("click", async () => {
      errorBox.hidden = true;
      const name = overlay.querySelector("#group-name").value.trim();
      if (!name) {
        errorBox.textContent = "群组名称不能为空";
        errorBox.hidden = false;
        return;
      }

      try {
        const group = await apiFetch("/api/groups", {
          method: "POST",
          body: JSON.stringify({
            name,
            group_type: overlay.querySelector("#group-type").value,
            description: overlay.querySelector("#group-desc").value.trim() || null,
          }),
        });
        close();
        await refreshWorkspace();
        state.selectedGroupId = group.id;
        const createdKb = state.knowledgeBases.find(
          (kb) => kb.scope_type === "enterprise_group" && kb.group_id === group.id
        );
        state.selectedKbId = createdKb ? createdKb.id : null;
        renderEnterprise();
      } catch (error) {
        errorBox.textContent = error.message;
        errorBox.hidden = false;
      }
    });
  });
}

function openCreateKnowledgeBaseModal(group) {
  openModal(`
    <h3>为「${escapeHtml(group.name)}」新建知识库</h3>
    <label>知识库名称<input id="kb-name" maxlength="150" value="${escapeHtml(group.name)}知识库"></label>
    <p class="error" id="form-error" hidden></p>
    <div class="modal-actions">
      <span class="spacer"></span>
      <button type="button" class="link" id="form-cancel">取消</button>
      <button type="button" class="primary" id="form-submit">创建</button>
    </div>
  `, (overlay, close) => {
    const errorBox = overlay.querySelector("#form-error");

    overlay.querySelector("#form-cancel").addEventListener("click", close);
    overlay.querySelector("#form-submit").addEventListener("click", async () => {
      errorBox.hidden = true;
      const name = overlay.querySelector("#kb-name").value.trim();
      if (!name) {
        errorBox.textContent = "知识库名称不能为空";
        errorBox.hidden = false;
        return;
      }

      try {
        const knowledgeBase = await apiFetch("/api/knowledge-bases", {
          method: "POST",
          body: JSON.stringify({
            name,
            scope_type: "enterprise_group",
            group_id: group.id,
          }),
        });
        close();
        await refreshWorkspace();
        state.selectedGroupId = group.id;
        state.selectedKbId = knowledgeBase.id;
        renderEnterprise();
      } catch (error) {
        errorBox.textContent = error.message;
        errorBox.hidden = false;
      }
    });
  });
}

function openCreatePersonalKbModal() {
  openModal(`
    <h3>新建个人知识库</h3>
    <label>知识库名称<input id="kb-name" maxlength="150" value="我的个人知识库"></label>
    <p class="error" id="form-error" hidden></p>
    <div class="modal-actions">
      <span class="spacer"></span>
      <button type="button" class="link" id="form-cancel">取消</button>
      <button type="button" class="primary" id="form-submit">创建</button>
    </div>
  `, (overlay, close) => {
    const errorBox = overlay.querySelector("#form-error");

    overlay.querySelector("#form-cancel").addEventListener("click", close);
    overlay.querySelector("#form-submit").addEventListener("click", async () => {
      errorBox.hidden = true;
      const name = overlay.querySelector("#kb-name").value.trim();
      if (!name) {
        errorBox.textContent = "知识库名称不能为空";
        errorBox.hidden = false;
        return;
      }

      try {
        const knowledgeBase = await apiFetch("/api/knowledge-bases", {
          method: "POST",
          body: JSON.stringify({ name, scope_type: "personal" }),
        });
        close();
        await refreshWorkspace();
        state.selectedKbId = knowledgeBase.id;
        renderPersonal();
      } catch (error) {
        errorBox.textContent = error.message;
        errorBox.hidden = false;
      }
    });
  });
}

async function openMembersModal(group, onChanged) {
  openModal(`
    <h3>「${escapeHtml(group.name)}」成员管理</h3>
    <div id="member-list"><div class="empty">加载中…</div></div>
    <div class="member-add">
      <input id="member-username" maxlength="50" placeholder="用户名（至少 2 个字符）">
      <select id="member-role">
        <option value="member">成员</option>
        <option value="editor">编辑者</option>
        <option value="admin">管理员</option>
      </select>
      <button type="button" class="secondary" id="member-add-btn">添加</button>
    </div>
    <p class="error" id="member-error" hidden></p>
    <div class="modal-actions">
      <span class="spacer"></span>
      <button type="button" class="link" id="member-close">关闭</button>
    </div>
  `, async (overlay, close) => {
    const listBox = overlay.querySelector("#member-list");
    const errorBox = overlay.querySelector("#member-error");

    const showError = (error) => {
      errorBox.textContent = error.message;
      errorBox.hidden = false;
    };

    const loadMembers = async () => {
      const members = await apiFetch(`/api/groups/${group.id}/members`);
      listBox.innerHTML = members.length
        ? members.map((member) => `
            <div class="member-row">
              <span class="member-name">${escapeHtml(member.username)}</span>
              <select data-role-select="${member.user_id}">
                ${["member", "editor", "admin"].map((role) => `
                  <option value="${role}" ${role === member.role ? "selected" : ""}>${roleLabel(role)}</option>
                `).join("")}
              </select>
              <button type="button" class="danger" data-remove="${member.user_id}">移除</button>
            </div>
          `).join("")
        : '<div class="empty">暂无成员</div>';
    };

    overlay.querySelector("#member-close").addEventListener("click", close);

    overlay.querySelector("#member-add-btn").addEventListener("click", async () => {
      errorBox.hidden = true;
      const username = overlay.querySelector("#member-username").value.trim();
      if (!username) {
        return;
      }
      try {
        await apiFetch(`/api/groups/${group.id}/members`, {
          method: "POST",
          body: JSON.stringify({
            username,
            role: overlay.querySelector("#member-role").value,
          }),
        });
        overlay.querySelector("#member-username").value = "";
        await loadMembers();
        if (onChanged) {
          onChanged();
        }
      } catch (error) {
        showError(error);
      }
    });

    listBox.addEventListener("change", async (event) => {
      const select = event.target.closest("[data-role-select]");
      if (!select) {
        return;
      }
      errorBox.hidden = true;
      try {
        await apiFetch(`/api/groups/${group.id}/members/${select.dataset.roleSelect}`, {
          method: "PATCH",
          body: JSON.stringify({ role: select.value }),
        });
        if (onChanged) {
          onChanged();
        }
      } catch (error) {
        showError(error);
        await loadMembers();
      }
    });

    listBox.addEventListener("click", async (event) => {
      const button = event.target.closest("[data-remove]");
      if (!button) {
        return;
      }
      if (!confirm("确定移除该成员吗？")) {
        return;
      }
      errorBox.hidden = true;
      try {
        await apiFetch(`/api/groups/${group.id}/members/${button.dataset.remove}`, {
          method: "DELETE",
        });
        await loadMembers();
        if (onChanged) {
          onChanged();
        }
      } catch (error) {
        showError(error);
      }
    });

    try {
      await loadMembers();
    } catch (error) {
      showError(error);
    }
  });
}

init();
