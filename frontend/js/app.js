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
      <div class="card-list" id="kb-list">
        ${groupBases.length ? groupBases.map((kb) => `
          <div class="card ${kb.id === state.selectedKbId ? "selected" : ""}" data-kb-id="${kb.id}">
            <div class="title">${escapeHtml(kb.name)}</div>
            <div class="meta">企业知识库 · 创建于 ${kb.created_at.slice(0, 10)}</div>
          </div>
        `).join("") : '<div class="empty">该群组还没有知识库</div>'}
      </div>
    </div>

    <div class="panel">
      <h3>文档</h3>
      <div class="empty">文档列表与上传将在后续步骤接入</div>
    </div>
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
}

function renderPersonal() {
  setActiveNav("personal");
  const view = document.getElementById("view");
  const personalBases = state.knowledgeBases.filter((kb) => kb.scope_type === "personal");

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
      <div class="card-list" id="kb-list">
        ${personalBases.length ? personalBases.map((kb) => `
          <div class="card ${kb.id === state.selectedKbId ? "selected" : ""}" data-kb-id="${kb.id}">
            <div class="title">${escapeHtml(kb.name)}</div>
            <div class="meta">个人知识库 · 仅自己可见 · 创建于 ${kb.created_at.slice(0, 10)}</div>
          </div>
        `).join("") : '<div class="empty">你还没有个人知识库</div>'}
      </div>
    </div>

    <div class="panel">
      <h3>文档</h3>
      <div class="empty">文档列表与上传将在后续步骤接入</div>
    </div>
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
    <div class="panel chat-box">
      <div>
        <div class="meta muted">检索范围</div>
        <div class="title">${knowledgeBase ? escapeHtml(knowledgeBase.name) : "未指定（请从知识库页面发起提问）"}</div>
      </div>
      <div>
        <div class="meta muted">你的问题</div>
        <div class="title">${question ? escapeHtml(question) : "暂无问题"}</div>
      </div>
      <div class="empty">
        问答接口与来源展示将在后续步骤接入。<br>
        当前页面已经可以接收知识库页面传来的“问题 + 检索范围”。
      </div>
    </div>
  `;
}

init();
