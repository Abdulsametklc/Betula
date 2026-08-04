/**
 * Betula — çalışma oturumları hub
 */
(async function () {
  await Auth.consumeOAuthHandoff();
  if (!Auth.requireAuth("/?login=1")) return;

  const $ = (id) => document.getElementById(id);
  const KEY_VIEW = "betula_sessions_view";
  const KEY_SORT = "betula_sessions_sort";

  let editingId = null;
  let sessionsCache = [];
  let viewMode = localStorage.getItem(KEY_VIEW) === "list" ? "list" : "grid";
  let sortMode = localStorage.getItem(KEY_SORT) || "date-desc";
  if (!["date-desc", "date-asc", "name-asc", "name-desc"].includes(sortMode)) {
    sortMode = "date-desc";
  }

  function toast(msg, ms = 2800) {
    const el = $("toast");
    el.textContent = msg;
    el.classList.remove("hidden");
    clearTimeout(el._t);
    el._t = setTimeout(() => el.classList.add("hidden"), ms);
  }

  function formatDate(d) {
    if (!d) return "";
    try {
      const raw = String(d).trim().replace(" ", "T");
      const iso = /Z$|[+-]\d{2}:?\d{2}$/.test(raw) ? raw : `${raw}Z`;
      return new Date(iso).toLocaleString("tr-TR", {
        timeZone: "Europe/Istanbul",
        dateStyle: "medium",
        timeStyle: "short",
      });
    } catch {
      return String(d);
    }
  }

  function escapeHtml(s) {
    return String(s ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function openApp(sessionId) {
    Auth.setSessionId(sessionId);
    window.location.href = `/app?session=${sessionId}`;
  }

  function openModal(mode, sess) {
    editingId = mode === "edit" ? sess.id : null;
    $("modal-title").textContent = mode === "edit" ? "Oturumu düzenle" : "Yeni oturum";
    $("session-title").value = sess?.title || "";
    $("session-desc").value = sess?.description || "";
    const m = $("session-modal");
    m.classList.remove("hidden");
    m.classList.add("flex");
    setTimeout(() => $("session-title").focus(), 50);
  }

  function closeModal() {
    const m = $("session-modal");
    m.classList.add("hidden");
    m.classList.remove("flex");
    editingId = null;
  }

  function sortSessions(list) {
    const items = [...list];
    const titleOf = (s) => String(s.title || "").trim().toLocaleLowerCase("tr");
    const dateOf = (s) => {
      const t = Date.parse(s.created_at || s.updated_at || "");
      return Number.isFinite(t) ? t : 0;
    };

    items.sort((a, b) => {
      if (sortMode === "name-asc") {
        return titleOf(a).localeCompare(titleOf(b), "tr", { sensitivity: "base" });
      }
      if (sortMode === "name-desc") {
        return titleOf(b).localeCompare(titleOf(a), "tr", { sensitivity: "base" });
      }
      if (sortMode === "date-asc") {
        return dateOf(a) - dateOf(b);
      }
      return dateOf(b) - dateOf(a);
    });
    return items;
  }

  function syncToolbar() {
    const listBtn = $("view-list");
    const gridBtn = $("view-grid");
    const isList = viewMode === "list";
    listBtn.classList.toggle("is-active", isList);
    gridBtn.classList.toggle("is-active", !isList);
    listBtn.setAttribute("aria-pressed", isList ? "true" : "false");
    gridBtn.setAttribute("aria-pressed", isList ? "false" : "true");

    const host = $("sessions-list");
    host.classList.toggle("view-list", isList);
    host.classList.toggle("view-grid", !isList);

    const sortEl = $("sessions-sort");
    if (sortEl && sortEl.value !== sortMode) sortEl.value = sortMode;
  }

  function bindCardActions(host, list) {
    host.querySelectorAll("[data-open]").forEach((btn) => {
      btn.onclick = () => openApp(Number(btn.dataset.open));
    });
    host.querySelectorAll("[data-edit]").forEach((btn) => {
      btn.onclick = (e) => {
        e.stopPropagation();
        const sess = list.find((x) => x.id === Number(btn.dataset.edit));
        if (sess) openModal("edit", sess);
      };
    });
    host.querySelectorAll("[data-del]").forEach((btn) => {
      btn.onclick = async (e) => {
        e.stopPropagation();
        if (!confirm("Bu oturumu silmek istiyor musun?")) return;
        const id = Number(btn.dataset.del);
        try {
          await LI.sessionDelete(id);
          if (Auth.sessionId === id) Auth.setSessionId(null);
          toast("Oturum silindi");
          await load();
        } catch (err) {
          toast(err.message);
        }
      };
    });
  }

  function renderGridCard(s, delay) {
    return `
      <article class="session-card enter rounded-2xl p-5 flex flex-col gap-4" style="animation-delay:${delay}s">
        <button data-open="${s.id}" class="text-left flex-1">
          <div class="flex items-start justify-between gap-3 mb-3">
            <div class="w-11 h-11 rounded-xl bg-primary-container border border-outline-variant flex items-center justify-center shrink-0">
              <span class="material-symbols-outlined text-primary">forest</span>
            </div>
            <span class="text-[11px] text-on-surface-variant">${formatDate(s.created_at || s.updated_at)}</span>
          </div>
          <h3 class="text-[17px] font-semibold text-on-surface leading-snug mb-1">${escapeHtml(s.title || "Oturum")}</h3>
          <p class="text-[13px] text-on-surface-variant line-clamp-2 min-h-[2.5em]">${escapeHtml(s.description || "Açıklama yok")}</p>
        </button>
        <div class="flex items-center gap-3 text-[12px] text-on-surface-variant border-t border-outline-variant pt-3">
          <span class="inline-flex items-center gap-1"><span class="material-symbols-outlined text-[14px]">description</span>${s.doc_count || 0}</span>
          <span class="inline-flex items-center gap-1"><span class="material-symbols-outlined text-[14px]">chat</span>${s.chat_count || 0}</span>
          <span class="inline-flex items-center gap-1"><span class="material-symbols-outlined text-[14px]">quiz</span>${s.quiz_count || 0}</span>
          <div class="ml-auto flex gap-1">
            <button data-edit="${s.id}" class="p-1.5 rounded-lg hover:bg-surface-container" title="Düzenle">
              <span class="material-symbols-outlined text-[16px]">edit</span>
            </button>
            <button data-del="${s.id}" class="p-1.5 rounded-lg hover:bg-surface-container text-red-700" title="Sil">
              <span class="material-symbols-outlined text-[16px]">delete</span>
            </button>
          </div>
        </div>
      </article>`;
  }

  function renderListRow(s, delay) {
    return `
      <article class="session-card enter session-row rounded-2xl" style="animation-delay:${delay}s">
        <button data-open="${s.id}" class="session-row-main">
          <div class="flex items-start gap-3">
            <div class="w-10 h-10 rounded-xl bg-primary-container border border-outline-variant flex items-center justify-center shrink-0">
              <span class="material-symbols-outlined text-primary text-[20px]">forest</span>
            </div>
            <div class="min-w-0 flex-1">
              <div class="flex items-center justify-between gap-3">
                <h3 class="text-[16px] font-semibold text-on-surface truncate">${escapeHtml(s.title || "Oturum")}</h3>
                <span class="text-[11px] text-on-surface-variant shrink-0 hidden sm:inline">${formatDate(s.created_at || s.updated_at)}</span>
              </div>
              <p class="text-[13px] text-on-surface-variant line-clamp-1 mt-0.5">${escapeHtml(s.description || "Açıklama yok")}</p>
              <div class="session-row-meta">
                <span class="sm:hidden">${formatDate(s.created_at || s.updated_at)}</span>
                <span class="inline-flex items-center gap-1"><span class="material-symbols-outlined text-[14px]">description</span>${s.doc_count || 0}</span>
                <span class="inline-flex items-center gap-1"><span class="material-symbols-outlined text-[14px]">chat</span>${s.chat_count || 0}</span>
                <span class="inline-flex items-center gap-1"><span class="material-symbols-outlined text-[14px]">quiz</span>${s.quiz_count || 0}</span>
              </div>
            </div>
          </div>
        </button>
        <div class="session-row-actions">
          <button data-edit="${s.id}" class="p-2 rounded-lg hover:bg-surface-container" title="Düzenle">
            <span class="material-symbols-outlined text-[18px]">edit</span>
          </button>
          <button data-del="${s.id}" class="p-2 rounded-lg hover:bg-surface-container text-red-700" title="Sil">
            <span class="material-symbols-outlined text-[18px]">delete</span>
          </button>
        </div>
      </article>`;
  }

  function renderSessions(list) {
    const host = $("sessions-list");
    syncToolbar();

    if (!list.length) {
      host.innerHTML = `
        <div class="session-card rounded-2xl p-10 text-center ${viewMode === "grid" ? "" : ""}" style="grid-column: 1 / -1">
          <img src="/static/assets/betula-logo.png" alt="" class="w-16 h-16 mx-auto mb-4 object-contain opacity-90"/>
          <h3 class="text-lg font-semibold mb-2">Henüz oturum yok</h3>
          <p class="text-sm text-on-surface-variant mb-5">İlk çalışma alanını oluşturup kaynak yüklemeye başla.</p>
          <button id="empty-new" class="primary-btn px-5 py-2.5 rounded-xl text-sm font-semibold">Yeni oturum oluştur</button>
        </div>`;
      $("empty-new").onclick = () => openModal("create");
      return;
    }

    const sorted = sortSessions(list);
    host.innerHTML = sorted
      .map((s, i) => {
        const delay = Math.min(i * 0.05, 0.35);
        return viewMode === "list" ? renderListRow(s, delay) : renderGridCard(s, delay);
      })
      .join("");

    bindCardActions(host, sorted);
  }

  function setView(mode) {
    viewMode = mode === "list" ? "list" : "grid";
    localStorage.setItem(KEY_VIEW, viewMode);
    renderSessions(sessionsCache);
  }

  function setSort(mode) {
    sortMode = mode;
    localStorage.setItem(KEY_SORT, sortMode);
    renderSessions(sessionsCache);
  }

  async function load() {
    try {
      sessionsCache = await LI.sessions();
      renderSessions(sessionsCache);
    } catch (e) {
      if (e.status === 401) {
        Auth.clear();
        location.href = "/?login=1";
        return;
      }
      $("sessions-list").innerHTML = `<p class="text-sm text-red-700">${escapeHtml(e.message)}</p>`;
    }
  }

  $("view-list").onclick = () => setView("list");
  $("view-grid").onclick = () => setView("grid");
  $("sessions-sort").onchange = (e) => setSort(e.target.value);

  $("btn-new-session").onclick = () => openModal("create");
  $("modal-cancel").onclick = closeModal;
  $("session-modal").onclick = (e) => {
    if (e.target === $("session-modal")) closeModal();
  };
  $("modal-save").onclick = async () => {
    const title = $("session-title").value.trim() || "Yeni Çalışma";
    const description = $("session-desc").value.trim();
    try {
      if (editingId) {
        await LI.sessionUpdate(editingId, { title, description });
        toast("Oturum güncellendi");
      } else {
        const sess = await LI.sessionCreate({ title, description });
        toast("Oturum oluşturuldu");
        closeModal();
        openApp(sess.id);
        return;
      }
      closeModal();
      await load();
    } catch (e) {
      toast(e.message);
    }
  };

  syncToolbar();
  if (window.ProfileMenu) {
    ProfileMenu.mount();
  }
  load();
})();
