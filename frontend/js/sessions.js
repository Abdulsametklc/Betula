/**
 * Betula — çalışma oturumları hub
 */
(async function () {
  await Auth.consumeOAuthHandoff();
  if (!Auth.requireAuth("/?login=1")) return;

  const $ = (id) => document.getElementById(id);
  let editingId = null;

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
      return new Date(d).toLocaleString("tr-TR", { dateStyle: "medium", timeStyle: "short" });
    } catch {
      return String(d);
    }
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

  function renderSessions(list) {
    const grid = $("sessions-grid");
    if (!list.length) {
      grid.innerHTML = `
        <div class="col-span-full session-card rounded-2xl p-10 text-center">
          <img src="/static/assets/betula-logo.png" alt="" class="w-16 h-16 mx-auto mb-4 object-contain opacity-90"/>
          <h3 class="text-lg font-semibold mb-2">Henüz oturum yok</h3>
          <p class="text-sm text-on-surface-variant mb-5">İlk çalışma alanını oluşturup kaynak yüklemeye başla.</p>
          <button id="empty-new" class="primary-btn px-5 py-2.5 rounded-xl text-sm font-semibold">Yeni oturum oluştur</button>
        </div>`;
      $("empty-new").onclick = () => openModal("create");
      return;
    }

    grid.innerHTML = list
      .map((s, i) => {
        const delay = Math.min(i * 0.06, 0.36);
        return `
        <article class="session-card enter rounded-2xl p-5 flex flex-col gap-4" style="animation-delay:${delay}s">
          <button data-open="${s.id}" class="text-left flex-1">
            <div class="flex items-start justify-between gap-3 mb-3">
              <div class="w-11 h-11 rounded-xl bg-primary-container border border-outline-variant flex items-center justify-center shrink-0">
                <span class="material-symbols-outlined text-primary">forest</span>
              </div>
              <span class="text-[11px] text-on-surface-variant">${formatDate(s.updated_at || s.created_at)}</span>
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
      })
      .join("");

    grid.querySelectorAll("[data-open]").forEach((btn) => {
      btn.onclick = () => openApp(Number(btn.dataset.open));
    });
    grid.querySelectorAll("[data-edit]").forEach((btn) => {
      btn.onclick = (e) => {
        e.stopPropagation();
        const sess = list.find((x) => x.id === Number(btn.dataset.edit));
        if (sess) openModal("edit", sess);
      };
    });
    grid.querySelectorAll("[data-del]").forEach((btn) => {
      btn.onclick = async (e) => {
        e.stopPropagation();
        if (!confirm("Bu oturumu silmek istiyor musun?")) return;
        try {
          await LI.sessionDelete(Number(btn.dataset.del));
          toast("Oturum silindi");
          await load();
        } catch (err) {
          toast(err.message);
        }
      };
    });
  }

  function escapeHtml(s) {
    return String(s ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  async function load() {
    try {
      const list = await LI.sessions();
      renderSessions(list);
    } catch (e) {
      if (e.status === 401) {
        Auth.clear();
        location.href = "/?login=1";
        return;
      }
      $("sessions-grid").innerHTML = `<p class="text-sm text-red-700">${escapeHtml(e.message)}</p>`;
    }
  }

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

  if (window.ProfileMenu) {
    ProfileMenu.mount();
  }
  load();
})();
