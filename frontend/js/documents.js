import { state, canEditKnowledgeBase } from "./state.js";
import {
  escapeHtml,
  showToast,
  confirmDialog,
  documentStatus,
} from "./ui.js";

export async function loadDocuments(knowledgeBase) {
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
  let fileBlob = null;
  downloadButton.disabled = true;
  downloadButton.addEventListener("click", () => {
    if (fileBlob) {
      downloadBlob(fileBlob, documentData.original_filename || documentData.title);
    }
  });

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
      if (!(await confirmDialog(`确定删除《${documentData.title}》吗？`, "删除"))) {
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
      fileBlob = await fetchDocumentBlob(documentData.id);
      downloadButton.disabled = false;

      if (documentData.file_type === "pdf") {
        objectUrl = URL.createObjectURL(fileBlob);
        container.innerHTML = `<embed class="pdf-embed" type="application/pdf" src="${objectUrl}">`;
      } else {
        const text = await fileBlob.text();
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
      if (!(await confirmDialog(`确定删除《${documentData.title}》吗？`, "删除"))) {
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

export function openDocumentEditor(knowledgeBase, documentData) {
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
