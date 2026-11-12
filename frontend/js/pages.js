import { state, refreshWorkspace } from "./state.js";
import { escapeHtml, roleLabel, setActiveNav, showToast } from "./ui.js";
import {
  openCreateGroupModal,
  openCreateKnowledgeBaseModal,
  openCreatePersonalKbModal,
  openMembersModal,
} from "./manage.js";
import { loadDocuments } from "./documents.js";

async function handleGroupCreated(group) {
  await refreshWorkspace();
  state.selectedGroupId = group.id;
  const createdKb = state.knowledgeBases.find(
    (kb) => kb.scope_type === "enterprise_group" && kb.group_id === group.id
  );
  state.selectedKbId = createdKb ? createdKb.id : null;
  renderEnterprise();
}

async function handleKnowledgeBaseCreated(knowledgeBase, group) {
  await refreshWorkspace();
  state.selectedGroupId = group.id;
  state.selectedKbId = knowledgeBase.id;
  renderEnterprise();
}

async function handlePersonalKbCreated(knowledgeBase) {
  await refreshWorkspace();
  state.selectedKbId = knowledgeBase.id;
  renderPersonal();
}

export function renderEnterprise() {
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
    document.getElementById("new-group").addEventListener("click", () => openCreateGroupModal(handleGroupCreated));
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

  document.getElementById("new-group").addEventListener("click", () => openCreateGroupModal(handleGroupCreated));

  const newKbButton = document.getElementById("new-kb");
  if (newKbButton) {
    newKbButton.addEventListener("click", () => {
      openCreateKnowledgeBaseModal(group, (knowledgeBase) => handleKnowledgeBaseCreated(knowledgeBase, group));
    });
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

export function renderPersonal() {
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
    newPersonalKbButton.addEventListener("click", () => openCreatePersonalKbModal(handlePersonalKbCreated));
  }

  if (selectedKb) {
    loadDocuments(selectedKb);
  } else {
    document.getElementById("doc-panel").innerHTML = '<div class="empty">你还没有个人知识库</div>';
  }
}
