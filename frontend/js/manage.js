import { escapeHtml, roleLabel, confirmDialog } from "./ui.js";

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

export function openCreateGroupModal(onCreated) {
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
        if (onCreated) {
          await onCreated(group);
        }
      } catch (error) {
        errorBox.textContent = error.message;
        errorBox.hidden = false;
      }
    });
  });
}

export function openCreateKnowledgeBaseModal(group, onCreated) {
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
        if (onCreated) {
          await onCreated(knowledgeBase);
        }
      } catch (error) {
        errorBox.textContent = error.message;
        errorBox.hidden = false;
      }
    });
  });
}

export function openCreatePersonalKbModal(onCreated) {
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
        if (onCreated) {
          await onCreated(knowledgeBase);
        }
      } catch (error) {
        errorBox.textContent = error.message;
        errorBox.hidden = false;
      }
    });
  });
}

export async function openMembersModal(group, onChanged) {
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
      if (!(await confirmDialog("确定移除该成员吗？", "移除"))) {
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
