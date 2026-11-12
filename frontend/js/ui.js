const ROLE_LABELS = {
  admin: "管理员",
  editor: "编辑者",
  member: "成员",
};

export function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (char) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  }[char]));
}

export function roleLabel(role) {
  return ROLE_LABELS[role] || role;
}

export function showToast(message, tone = "info") {
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

export function confirmDialog(message, confirmText = "确定") {
  return new Promise((resolve) => {
    const overlay = document.createElement("div");
    overlay.className = "modal-overlay";
    overlay.innerHTML = `
      <div class="modal modal-confirm" role="dialog" aria-modal="true" aria-label="操作确认">
        <h3>请确认</h3>
        <p>${escapeHtml(message)}</p>
        <div class="modal-actions">
          <span class="spacer"></span>
          <button type="button" class="secondary" data-confirm-cancel>取消</button>
          <button type="button" class="danger" data-confirm-ok>${escapeHtml(confirmText)}</button>
        </div>
      </div>
    `;
    const finish = (value) => {
      document.removeEventListener("keydown", onKey);
      overlay.remove();
      resolve(value);
    };
    const onKey = (event) => {
      if (event.key === "Escape") {
        finish(false);
      }
    };
    overlay.addEventListener("click", (event) => {
      if (event.target === overlay || event.target.closest("[data-confirm-cancel]")) {
        finish(false);
      } else if (event.target.closest("[data-confirm-ok]")) {
        finish(true);
      }
    });
    document.addEventListener("keydown", onKey);
    document.body.appendChild(overlay);
    overlay.querySelector("[data-confirm-ok]").focus();
  });
}

export function documentStatus(status) {
  const values = {
    READY: ["已就绪", "ready"],
    PROCESSING: ["处理中", "processing"],
    FAILED: ["处理失败", "failed"],
    UPLOADED: ["待处理", "processing"],
  };
  return values[status] || [status || "未知状态", "processing"];
}

export function setActiveNav(name) {
  document.querySelectorAll("[data-nav]").forEach((link) => {
    link.classList.toggle("active", link.dataset.nav === name);
  });
}
