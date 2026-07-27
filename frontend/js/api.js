/**
 * LocalInsights API client
 */
const API_BASE = window.LOCALINSIGHTS_API || `${window.location.origin}`;

const Auth = {
  tokenKey: "li_token",
  userKey: "li_user",
  sessionKey: "li_session_id",

  get token() {
    return localStorage.getItem(this.tokenKey);
  },
  get user() {
    try {
      return JSON.parse(localStorage.getItem(this.userKey) || "null");
    } catch {
      return null;
    }
  },
  get sessionId() {
    const v = localStorage.getItem(this.sessionKey);
    return v ? Number(v) : null;
  },
  setSession(token, user) {
    localStorage.setItem(this.tokenKey, token);
    localStorage.setItem(this.userKey, JSON.stringify(user));
  },
  setUser(user) {
    localStorage.setItem(this.userKey, JSON.stringify(user));
  },
  setSessionId(id) {
    if (id == null) localStorage.removeItem(this.sessionKey);
    else localStorage.setItem(this.sessionKey, String(id));
  },
  clear() {
    localStorage.removeItem(this.tokenKey);
    localStorage.removeItem(this.userKey);
    localStorage.removeItem(this.sessionKey);
  },
  isLoggedIn() {
    return Boolean(this.token);
  },
  initial() {
    const u = this.user;
    const src = (u?.name || u?.username || u?.email || "U").trim();
    return (src[0] || "U").toUpperCase();
  },
  avatarSrc(user = this.user) {
    if (!user) return null;
    if (user.avatar_type === "image" && user.avatar_value) {
      return `${API_BASE}/media/avatars/${encodeURIComponent(user.avatar_value)}`;
    }
    return null;
  },
  requireAuth(redirectTo = "/") {
    if (!this.isLoggedIn()) {
      window.location.href = redirectTo + (redirectTo.includes("?") ? "&" : "?") + "login=1";
      return false;
    }
    return true;
  },
  requireSession(redirectTo = "/oturumlar") {
    if (!this.requireAuth("/?login=1")) return false;
    if (!this.sessionId) {
      window.location.href = redirectTo;
      return false;
    }
    return true;
  },
  async consumeOAuthHandoff() {
    const params = new URLSearchParams(location.search);
    const token = params.get("oauth_token");
    if (!token) return false;
    localStorage.setItem(this.tokenKey, token);
    try {
      const headers = { Authorization: `Bearer ${token}` };
      const res = await fetch(`${API_BASE}/auth/me`, { headers });
      if (!res.ok) throw new Error("OAuth oturumu kurulamadi");
      const user = await res.json();
      this.setSession(token, user);
    } catch {
      this.clear();
      return false;
    }
    params.delete("oauth_token");
    const qs = params.toString();
    history.replaceState({}, "", `${location.pathname}${qs ? `?${qs}` : ""}${location.hash}`);
    return true;
  },
};

async function api(path, options = {}) {
  const headers = { ...(options.headers || {}) };
  if (!(options.body instanceof FormData)) {
    headers["Content-Type"] = headers["Content-Type"] || "application/json";
  }
  if (Auth.token) {
    headers["Authorization"] = `Bearer ${Auth.token}`;
  }
  if (!options.skipSession && Auth.sessionId) {
    headers["X-Session-Id"] = String(Auth.sessionId);
  }

  const res = await fetch(`${API_BASE}${path}`, { ...options, headers });
  const text = await res.text();
  let data = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = text;
  }

  if (!res.ok) {
    const detail = data?.detail || data?.message || res.statusText || "İstek başarısız";
    const err = new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
    err.status = res.status;
    err.data = data;
    throw err;
  }
  return data;
}

const LI = {
  register: (email, password, name) =>
    api("/auth/register", { method: "POST", body: JSON.stringify({ email, password, name }), skipSession: true }),
  login: (email, password) =>
    api("/auth/login", { method: "POST", body: JSON.stringify({ email, password }), skipSession: true }),
  oauthProviders: () => api("/auth/oauth/providers", { skipSession: true }),
  oauthStartUrl: (provider) => `${API_BASE}/auth/oauth/${encodeURIComponent(provider)}/start`,
  me: () => api("/auth/me", { skipSession: true }),
  updateProfile: (payload) =>
    api("/auth/profile", { method: "PATCH", body: JSON.stringify(payload), skipSession: true }),
  requestSecurityCode: (purpose) =>
    api("/auth/security/request-code", {
      method: "POST",
      body: JSON.stringify({ purpose }),
      skipSession: true,
    }),
  verifySecurityCode: (purpose, code) =>
    api("/auth/security/verify-code", {
      method: "POST",
      body: JSON.stringify({ purpose, code }),
      skipSession: true,
    }),
  confirmEmailChange: (code, new_email) =>
    api("/auth/security/confirm-email", {
      method: "POST",
      body: JSON.stringify({ code, new_email }),
      skipSession: true,
    }),
  confirmPasswordChange: (code, new_password) =>
    api("/auth/security/confirm-password", {
      method: "POST",
      body: JSON.stringify({ code, new_password }),
      skipSession: true,
    }),
  forgotPassword: (identifier) =>
    api("/auth/forgot-password", {
      method: "POST",
      body: JSON.stringify({ identifier }),
      skipSession: true,
    }),
  verifyResetCode: (identifier, code) =>
    api("/auth/reset-password/verify", {
      method: "POST",
      body: JSON.stringify({ identifier, code }),
      skipSession: true,
    }),
  resetPassword: (identifier, code, new_password) =>
    api("/auth/reset-password", {
      method: "POST",
      body: JSON.stringify({ identifier, code, new_password }),
      skipSession: true,
    }),
  changePassword: (old_password, new_password) =>
    api("/auth/change-password", {
      method: "POST",
      body: JSON.stringify({ old_password, new_password }),
      skipSession: true,
    }),
  uploadAvatar: (file) => {
    const fd = new FormData();
    fd.append("file", file);
    return api("/auth/avatar", { method: "POST", body: fd, skipSession: true });
  },
  setAvatarIcon: (icon) =>
    api("/auth/avatar/icon", { method: "POST", body: JSON.stringify({ icon }), skipSession: true }),
  clearAvatar: () => api("/auth/avatar", { method: "DELETE", skipSession: true }),
  avatarIcons: () => api("/auth/avatar-icons", { skipSession: true }),
  sessions: () => api("/sessions", { skipSession: true }),
  sessionCreate: (payload) =>
    api("/sessions", { method: "POST", body: JSON.stringify(payload), skipSession: true }),
  sessionUpdate: (id, payload) =>
    api(`/sessions/${id}`, { method: "PATCH", body: JSON.stringify(payload), skipSession: true }),
  sessionDelete: (id) =>
    api(`/sessions/${id}`, { method: "DELETE", skipSession: true }),
  sessionGet: (id) => api(`/sessions/${id}`, { skipSession: true }),
  documents: () => api("/documents"),
  upload: (file, autoCompile = true) => {
    const fd = new FormData();
    fd.append("file", file);
    return api(`/documents/upload?auto_compile=${autoCompile}`, { method: "POST", body: fd });
  },
  compile: (id) => api(`/documents/${id}/compile`, { method: "POST" }),
  job: (id) => api(`/pipeline/jobs/${id}`),
  compiledNote: (id) => api(`/documents/${id}/compiled-note`),
  downloadCompiledNote: async (id, { format = "docx", kind = "note" } = {}) => {
    const q = new URLSearchParams({ format, kind });
    const res = await fetch(
      `${API_BASE}/documents/${id}/compiled-note/download?${q}`,
      { headers: { Authorization: `Bearer ${Auth.token}`, "X-Session-Id": String(Auth.sessionId || "") } }
    );
    if (!res.ok) {
      let detail = "Indirme basarisiz";
      try {
        const data = await res.json();
        detail = data?.detail || detail;
      } catch {
        /* ignore */
      }
      throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
    }
    const blob = await res.blob();
    const dispo = res.headers.get("Content-Disposition") || "";
    const match = /filename=\"?([^\";]+)\"?/i.exec(dispo);
    const filename = match?.[1] || `betula_${id}.${format}`;
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = filename;
    a.click();
    URL.revokeObjectURL(a.href);
  },
  conversations: () => api("/conversations"),
  createConversation: (title) =>
    api("/conversations", { method: "POST", body: JSON.stringify({ title }) }),
  deleteConversation: (id) =>
    api(`/conversations/${id}`, { method: "DELETE", skipSession: false }),
  messages: (id) => api(`/conversations/${id}/messages`),
  chat: (payload) =>
    api("/chat/completions", { method: "POST", body: JSON.stringify(payload) }),
  chatStream: async (payload, handlers = {}) => {
    const headers = { "Content-Type": "application/json", Accept: "text/event-stream" };
    if (Auth.token) headers.Authorization = `Bearer ${Auth.token}`;
    if (Auth.sessionId) headers["X-Session-Id"] = String(Auth.sessionId);

    const res = await fetch(`${API_BASE}/chat/completions/stream`, {
      method: "POST",
      headers,
      body: JSON.stringify(payload),
    });

    if (!res.ok) {
      const text = await res.text();
      let detail = res.statusText;
      try {
        const data = JSON.parse(text);
        detail = data?.detail || data?.message || detail;
      } catch {
        if (text) detail = text;
      }
      throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let donePayload = null;

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const chunks = buffer.split("\n\n");
      buffer = chunks.pop() || "";

      for (const chunk of chunks) {
        if (!chunk.trim() || chunk.startsWith(":")) continue;
        let event = "message";
        let dataLine = "";
        for (const line of chunk.split("\n")) {
          if (line.startsWith("event:")) event = line.slice(6).trim();
          else if (line.startsWith("data:")) dataLine += line.slice(5).trim();
        }
        if (!dataLine) continue;
        let data;
        try {
          data = JSON.parse(dataLine);
        } catch {
          continue;
        }
        if (event === "meta" && handlers.onMeta) handlers.onMeta(data);
        else if (event === "status" && handlers.onStatus) handlers.onStatus(data.text || "");
        else if (event === "token" && handlers.onToken) handlers.onToken(data.text || "");
        else if (event === "error" && handlers.onError) handlers.onError(data.detail || "Stream hatası");
        else if (event === "done") {
          donePayload = data;
          if (handlers.onDone) handlers.onDone(data);
        }
      }
    }
    return donePayload;
  },
  flashcardsReview: (limit = 50, docId = null) =>
    api(`/flashcards/review?limit=${limit}${docId ? `&document_id=${docId}` : ""}`),
  flashcardsGenerate: (docId, count = 10) =>
    api(`/documents/${docId}/flashcards/generate`, {
      method: "POST",
      body: JSON.stringify({ count }),
    }),
  flashcardReview: (id, knew) =>
    api(`/flashcards/${id}/review`, { method: "POST", body: JSON.stringify({ knew }) }),
  quizRandom: (docId, limit = 5) =>
    api(`/quiz/random?limit=${limit}${docId ? `&document_id=${docId}` : ""}`),
  quizGenerate: (docId, count = 10, topic = null) =>
    api(`/documents/${docId}/quiz/generate`, {
      method: "POST",
      body: JSON.stringify({ count, topic: topic || null }),
    }),
  quizAnswer: (id, answer) =>
    api(`/quiz/${id}/answer`, { method: "POST", body: JSON.stringify({ answer }) }),
  quizAttemptCreate: (payload) =>
    api("/quiz/attempts", { method: "POST", body: JSON.stringify(payload) }),
  quizAttempts: () => api("/quiz/attempts"),
  quizAttempt: (id) => api(`/quiz/attempts/${id}`),
  quizAttemptDelete: (id) => api(`/quiz/attempts/${id}`, { method: "DELETE" }),
  stats: () => api("/stats/learning"),
};

window.Auth = Auth;
window.LI = LI;
window.api = api;
