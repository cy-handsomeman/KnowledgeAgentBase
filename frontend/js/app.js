import { state } from "./state.js";
import { escapeHtml } from "./ui.js";
import { renderEnterprise, renderPersonal } from "./pages.js";
import { renderChat } from "./chat.js";

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

init();
