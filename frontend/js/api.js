function getToken() {
  return localStorage.getItem("token");
}

async function apiFetch(path, options = {}) {
  const headers = {
    "Content-Type": "application/json",
    ...(options.headers || {}),
  };
  const token = getToken();
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }

  const response = await fetch(path, { ...options, headers });

  if (response.status === 401) {
    localStorage.removeItem("token");
    if (!location.pathname.endsWith("/login.html")) {
      location.href = "/login.html";
    }
    throw new Error("登录已失效，请重新登录");
  }

  if (!response.ok) {
    let detail = `${response.status} ${response.statusText}`;
    try {
      const body = await response.json();
      if (body.detail) {
        detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
      }
    } catch (error) {
      // 响应不是 JSON 时保留状态码信息
    }
    throw new Error(detail);
  }

  return response.json();
}

function requireLogin() {
  if (!getToken()) {
    location.href = "/login.html";
  }
}
