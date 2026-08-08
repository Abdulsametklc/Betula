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
  let viewMode = localStorage.getItem(KEY_VIEW) === "grid" ? "grid" : "list";
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
      <article class="glass-panel rounded-xl p-md flex flex-col gap-3 hover:border-tertiary-fixed-dim transition-all group" style="animation-delay:${delay}s">
        <button data-open="${s.id}" class="text-left flex-1">
          <div class="flex items-start justify-between gap-3 mb-2">
            <div class="w-10 h-10 rounded-full bg-tertiary-fixed/40 text-on-tertiary-container flex items-center justify-center shrink-0">
              <span class="material-symbols-outlined" style="font-variation-settings:'FILL' 1">eco</span>
            </div>
            <span class="text-[12px] text-secondary">${formatDate(s.created_at || s.updated_at)}</span>
          </div>
          <h3 class="font-headline-md text-[18px] text-primary leading-snug mb-1">${escapeHtml(s.title || "Oturum")}</h3>
          <p class="text-[14px] text-secondary line-clamp-2 min-h-[2.5em]">${escapeHtml(s.description || "Açıklama yok")}</p>
        </button>
        <div class="flex items-center gap-3 text-[13px] text-secondary border-t border-outline-variant/30 pt-3">
          <span class="inline-flex items-center gap-1"><span class="material-symbols-outlined text-[18px]">description</span>${s.doc_count || 0}</span>
          <span class="inline-flex items-center gap-1"><span class="material-symbols-outlined text-[18px]">chat</span>${s.chat_count || 0}</span>
          <span class="inline-flex items-center gap-1"><span class="material-symbols-outlined text-[18px]">quiz</span>${s.quiz_count || 0}</span>
          <div class="ml-auto flex gap-1 opacity-100 md:opacity-0 md:group-hover:opacity-100 transition-opacity">
            <button data-edit="${s.id}" class="p-2 rounded-full hover:bg-surface-container-highest text-secondary" title="Düzenle">
              <span class="material-symbols-outlined text-[18px]">edit</span>
            </button>
            <button data-del="${s.id}" class="p-2 rounded-full hover:bg-error-container text-secondary hover:text-error" title="Sil">
              <span class="material-symbols-outlined text-[18px]">delete</span>
            </button>
          </div>
        </div>
      </article>`;
  }

  function renderListRow(s, delay) {
    const isActive = Auth.sessionId === s.id;
    return `
      <article class="glass-panel rounded-xl p-md flex flex-col md:flex-row justify-between items-start md:items-center gap-sm hover:border-tertiary-fixed-dim transition-all group" style="animation-delay:${delay}s">
        <button data-open="${s.id}" class="text-left min-w-0 flex-1">
          <h3 class="font-headline-md text-[18px] text-primary mb-xs">${escapeHtml(s.title || "Oturum")}</h3>
          <p class="font-body-md text-body-md text-secondary">${formatDate(s.created_at || s.updated_at)}</p>
          ${s.description ? `<p class="text-[13px] text-secondary/80 mt-1 line-clamp-1">${escapeHtml(s.description)}</p>` : ""}
        </button>
        <div class="flex items-center gap-md flex-wrap">
          <div class="flex items-center gap-xs text-secondary"><span class="material-symbols-outlined text-[20px]">description</span>${s.doc_count || 0}</div>
          <div class="flex items-center gap-xs text-secondary"><span class="material-symbols-outlined text-[20px]">chat</span>${s.chat_count || 0}</div>
          <div class="flex items-center gap-xs text-secondary"><span class="material-symbols-outlined text-[20px]">quiz</span>${s.quiz_count || 0}</div>
          ${isActive ? `<span class="px-3 py-1 rounded-full bg-tertiary-fixed-dim/20 text-on-tertiary-container font-label-caps text-label-caps ml-sm">Aktif</span>` : ""}
          <div class="flex gap-xs ml-sm opacity-100 md:opacity-0 md:group-hover:opacity-100 transition-opacity">
            <button data-edit="${s.id}" class="p-2 rounded-full hover:bg-surface-container-highest text-secondary" title="Düzenle">
              <span class="material-symbols-outlined">edit</span>
            </button>
            <button data-del="${s.id}" class="p-2 rounded-full hover:bg-error-container text-secondary hover:text-error" title="Sil">
              <span class="material-symbols-outlined">delete</span>
            </button>
          </div>
        </div>
      </article>`;
  }

  function renderSessions(list) {
    const host = $("sessions-list");
    syncToolbar();

    if (!list.length) {
      host.innerHTML = `
        <div class="glass-panel rounded-xl p-10 text-center" style="grid-column: 1 / -1">
          <span class="material-symbols-outlined text-[48px] text-on-tertiary-container mb-3 block" style="font-variation-settings:'FILL' 1">eco</span>
          <h3 class="text-lg font-semibold mb-2 text-primary">Henüz oturum yok</h3>
          <p class="text-sm text-secondary mb-5">İlk çalışma alanını oluşturup kaynak yüklemeye başla.</p>
          <button id="empty-new" class="primary-btn px-5 py-2.5 rounded-full text-sm font-semibold">Yeni oturum oluştur</button>
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
