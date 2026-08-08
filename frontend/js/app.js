/**
 * LocalInsights workspace controller
 */
(function () {
  // Oturum zorunlu: yoksa hub'a
  const params = new URLSearchParams(location.search);
  const qSession = params.get("session");
  if (qSession) Auth.setSessionId(Number(qSession));
  if (!Auth.requireSession("/oturumlar")) return;

  const state = {
    documents: [],
    conversations: [],
    selectedDocId: null,
    conversationId: null,
    currentJobId: null,
    pollTimer: null,
    flashcards: [],
    flashIndex: 0,
    flashFlipped: false,
    quiz: [],
    quizIndex: 0,
    quizTopic: "",
    quizCount: 10,
    quizAnswers: [],
  };

  const $ = (id) => document.getElementById(id);

  function toast(msg, ms = 3200) {
    const el = $("toast");
    el.textContent = msg;
    el.classList.remove("hidden");
    clearTimeout(el._t);
    el._t = setTimeout(() => el.classList.add("hidden"), ms);
  }

  function closeStudyModals() {
    ["modal-flashcards", "modal-quiz"].forEach((id) => {
      const el = $(id);
      if (!el) return;
      el.classList.add("is-hidden");
      el.setAttribute("aria-hidden", "true");
    });
    document.body.style.overflow = "";
  }

  function openStudyModal(kind) {
    closeStudyModals();
    const id = kind === "quiz" ? "modal-quiz" : "modal-flashcards";
    const el = $(id);
    if (!el) return;
    el.classList.remove("is-hidden");
    el.setAttribute("aria-hidden", "false");
    document.body.style.overflow = "hidden";
  }

  function setView(view) {
    const notes = $("panel-notes");
    if (notes) notes.classList.remove("panel-hidden");

    const markNav = (activeView) => {
      document.querySelectorAll("#nav-main .nav-btn[data-view]").forEach((btn) => {
        btn.classList.toggle("nav-active", btn.dataset.view === activeView);
      });
    };

    if (view === "flashcards") {
      openStudyModal("flashcards");
      markNav("flashcards");
      loadFlashcards();
      return;
    }
    if (view === "quiz") {
      openStudyModal("quiz");
      markNav("quiz");
      startQuizFlow();
      return;
    }

    closeStudyModals();
    markNav(view === "sources" ? "notes" : view || "notes");
  }

  function showSidebarPanel(which) {
    // which: 'main' | 'sources'
    const main = $("nav-main");
    const sources = $("nav-sources");
    [main, sources].forEach((el) => {
      if (!el) return;
      el.classList.add("hidden");
      el.classList.remove("flex");
    });
    const target = which === "sources" ? sources : main;
    if (target) {
      target.classList.remove("hidden");
      target.classList.add("flex");
    }
    if (which === "sources") {
      loadDocuments().catch(() => {});
    }
  }

  function renderSources() {
    const list = $("sources-list");
    if (!list) return;
    if (!state.documents.length) {
      list.innerHTML = `<p class="text-sm text-on-surface-variant px-2">Henüz kaynak yok. Ana menüden Yeni Kaynak ile yükle.</p>`;
      return;
    }
    list.innerHTML = state.documents
      .map((d) => {
        const active = d.id === state.selectedDocId;
        const iconBg = d.doc_type === "pdf" ? "bg-error-container text-on-error-container" : "bg-primary-container text-on-primary-container";
        const icon = d.doc_type === "pdf" ? "picture_as_pdf" : "description";
        return `
        <button data-doc-id="${d.id}" class="source-item w-full text-left rounded-lg border px-3 py-2.5 transition-all ${
          active ? "border-primary bg-primary-container/40" : "border-outline-variant bg-surface-container-lowest hover:border-primary"
        }">
          <span class="flex items-start gap-2">
            <span class="w-8 h-8 rounded ${iconBg} flex items-center justify-center shrink-0">
              <span class="material-symbols-outlined text-[16px]" style="font-variation-settings: 'FILL' 1;">${icon}</span>
            </span>
            <span class="min-w-0 overflow-hidden">
              <span class="block text-[13px] font-semibold text-on-surface truncate">${escapeHtml(d.filename)}</span>
              <span class="block text-[11px] text-on-surface-variant truncate mt-1">${d.is_processed ? "İşlendi" : "Bekliyor"} · ${formatDate(d.upload_date)}</span>
            </span>
          </span>
        </button>`;
      })
      .join("");

    list.querySelectorAll("[data-doc-id]").forEach((btn) => {
      btn.addEventListener("click", () => selectDocument(Number(btn.dataset.docId)));
    });
  }

  async function bindSessionChat() {
    state.conversations = await LI.conversations();
    const conv = state.conversations[0] || null;
    if (!conv) {
      state.conversationId = null;
      clearChat();
      return;
    }
    if (state.conversationId === conv.id && $("chat-messages")?.children.length) {
      return;
    }
    state.conversationId = conv.id;
    clearChat();
    const msgs = await LI.messages(conv.id);
    msgs.forEach((m) => appendChat(m.role, m.content));
  }

  async function loadConversations() {
    await bindSessionChat();
  }

  function formatChatHtml(content, { markdown = false } = {}) {
    const text = content == null ? "" : String(content);
    if (!markdown || typeof marked === "undefined") {
      return escapeHtml(text);
    }
    try {
      return marked.parse(text, { breaks: true });
    } catch {
      return escapeHtml(text);
    }
  }

  function appendChat(role, content) {
    const box = $("chat-messages");
    const isUser = role === "user";
    const wrap = document.createElement("div");
    wrap.className = isUser
      ? "flex items-start gap-3 self-end flex-row-reverse max-w-[85%]"
      : "flex items-start gap-3 max-w-[92%]";
    const bodyClass = isUser
      ? "bg-surface-container rounded-tr-none whitespace-pre-wrap"
      : "bg-surface-container rounded-tl-none chat-md [&_p]:my-1.5 [&_p:first-child]:mt-0 [&_p:last-child]:mb-0 [&_ul]:my-1.5 [&_ol]:my-1.5 [&_li]:my-0.5 [&_strong]:font-semibold [&_code]:text-[12px] [&_code]:bg-surface-container-high [&_code]:px-1 [&_code]:rounded";
    wrap.innerHTML = `
      <div class="w-8 h-8 rounded-full ${isUser ? "bg-surface-container" : "bg-primary-container text-on-primary-container border border-outline-variant"} flex items-center justify-center shrink-0">
        <span class="material-symbols-outlined text-[16px]">${isUser ? "person" : "robot_2"}</span>
      </div>
      <div data-chat-body data-markdown="${isUser ? "0" : "1"}" class="${bodyClass} p-3 rounded-lg text-[14px] leading-relaxed text-on-surface border border-outline-variant">${formatChatHtml(content, { markdown: !isUser })}</div>`;
    box.appendChild(wrap);
    box.scrollTop = box.scrollHeight;
    return wrap.querySelector("[data-chat-body]");
  }

  function setChatBody(el, content) {
    if (!el) return;
    const useMd = el.getAttribute("data-markdown") === "1";
    if (useMd) el.innerHTML = formatChatHtml(content, { markdown: true });
    else el.textContent = content;
    const box = $("chat-messages");
    box.scrollTop = box.scrollHeight;
  }

  function clearChat() {
    $("chat-messages").innerHTML = "";
  }

  async function loadDocuments() {
    state.documents = await LI.documents();
    renderSources();
    if (!state.selectedDocId && state.documents.length) {
      await selectDocument(state.documents[0].id);
    }
  }

  async function selectDocument(id) {
    state.selectedDocId = id;
    renderSources();
    const doc = state.documents.find((d) => d.id === id);
    $("doc-title").textContent = doc?.filename || `Özet`;
    $("btn-compile").disabled = false;
    showSidebarPanel("main");
    setView("notes");
    await loadCompiledNote(id);
  }

  async function loadCompiledNote(docId) {
    const noteBox = $("note-content");
    const gaps = $("gap-list");
    const exportNote = $("export-note-wrap");
    const exportMaster = $("export-master-wrap");
    try {
      const note = await LI.compiledNote(docId);
      const html = typeof marked !== "undefined" ? marked.parse(note.markdown || "") : escapeHtml(note.markdown || "");
      noteBox.innerHTML = `<div class="max-w-3xl mx-auto bg-surface-container-lowest border border-outline-variant rounded-lg p-8 shadow-md prose-note">${html}</div>`;
      renderGaps(note.gap_list || []);
      exportNote?.classList.remove("hidden");
      exportMaster?.classList.remove("hidden");
    } catch {
      noteBox.innerHTML = `<div class="max-w-3xl mx-auto bg-surface-container-lowest border border-outline-variant rounded-lg p-8 shadow-md prose-note">
        <h2 class="text-[22px] font-semibold mb-3">Derlenmiş not yok</h2>
        <p class="text-on-surface-variant mb-4">Bu kaynak henüz işlenmedi. “Derle” ile araştırma boru hattını başlat.</p>
      </div>`;
      gaps.innerHTML = `<li class="text-sm text-on-surface-variant">Henüz gap yok.</li>`;
      exportNote?.classList.add("hidden");
      exportMaster?.classList.add("hidden");
    }
  }

  function closeExportMenus() {
    $("export-note-menu")?.classList.add("hidden");
    $("export-master-menu")?.classList.add("hidden");
  }

  async function exportCurrent(kind, format) {
    if (!state.selectedDocId) {
      toast("Once bir kaynak sec");
      return;
    }
    try {
      await LI.downloadCompiledNote(state.selectedDocId, { kind, format });
      toast("Indirme basladi");
    } catch (e) {
      toast(e.message || "Indirme basarisiz");
    } finally {
      closeExportMenus();
    }
  }

  function renderGaps(gapItems) {
    const gaps = $("gap-list");
    if (!gapItems.length) {
      gaps.innerHTML = `<li class="text-sm text-on-surface-variant">Gap listesi boş.</li>`;
      return;
    }

    gaps.innerHTML = gapItems
      .map((g, i) => {
        const sources = (g.sources || []).filter((s) => s.href);
        const sourceLinks = sources.length
          ? `<div class="mt-2 pt-2 border-t border-outline-variant">
               <p class="text-[11px] uppercase tracking-wider text-on-surface-variant mb-1">Kaynaklar</p>
               ${sources
                 .map(
                   (s) =>
                     `<a href="${escapeAttr(s.href)}" target="_blank" rel="noopener" class="block text-[12px] text-primary hover:underline truncate">${escapeHtml(s.title || s.href)}</a>`
                 )
                 .join("")}
             </div>`
          : "";

        const body = g.summary
          ? `<p class="text-[13px] text-on-surface mt-2 whitespace-pre-wrap">${escapeHtml(g.summary)}</p>`
          : `<p class="text-[13px] text-on-surface-variant mt-2 italic">Bu konu için araştırma özeti yok.</p>`;

        return `
        <li class="bg-surface-container rounded-lg border-l-4 border-l-primary border border-outline-variant overflow-hidden">
          <button data-gap-toggle="${i}" class="w-full text-left p-3 flex items-start justify-between gap-2 hover:bg-surface-container-high transition-colors">
            <span class="min-w-0">
              <span class="block text-[13px] font-semibold text-on-surface">${escapeHtml(g.topic || "Konu")}${g.from_chat ? ' <span class="text-[10px] font-medium text-primary">· sohbet</span>' : ""}</span>
              <span class="block text-[12px] text-on-surface-variant mt-1">${escapeHtml(g.reason || "")}</span>
            </span>
            <span class="material-symbols-outlined text-[18px] text-on-surface-variant shrink-0" data-gap-icon="${i}">expand_more</span>
          </button>
          <div data-gap-body="${i}" class="hidden px-3 pb-3">
            ${body}
            ${sourceLinks}
          </div>
        </li>`;
      })
      .join("");

    gaps.querySelectorAll("[data-gap-toggle]").forEach((btn) => {
      btn.onclick = () => {
        const i = btn.dataset.gapToggle;
        const body = gaps.querySelector(`[data-gap-body="${i}"]`);
        const icon = gaps.querySelector(`[data-gap-icon="${i}"]`);
        const open = !body.classList.contains("hidden");
        body.classList.toggle("hidden", open);
        icon.textContent = open ? "expand_more" : "expand_less";
      };
    });
  }

  function pipelineMessage(status, step) {
    const s = String(step || "").toLowerCase();
    const st = String(status || "").toLowerCase();
    if (st === "failed" || s === "failed") return "Derleme başarısız oldu";
    if (st === "done" || s === "done") return "Master sentez hazır";
    if (st === "queued" || s === "başlıyor" || s === "basliyor") return "Derleme başlıyor…";
    if (s === "parse") return "Doküman taranıyor…";
    if (s === "gap_analysis") return "Eksikler tespit ediliyor…";
    if (s === "web_research") return "Eksikler tamamlanıyor…";
    if (s === "synthesis") return "Master sentez yazılıyor…";
    if (s === "persist") return "Notlar kaydediliyor…";
    if (st === "running") return "Kaynak derleniyor…";
    return "Kaynak derleniyor…";
  }

  const COMPILE_TIPS = [
    "Betula, huş ağacının Latince adıdır. Bilgelik ve yenilenmeyi simgeler.",
    "Kısa aralıklarla tekrar etmek, uzun oturumlardan daha kalıcı öğrenme sağlar.",
    "Okurken kendi cümlelerinle özetlemek, ezberden daha güçlü bir bellek izi bırakır.",
    "Beyin boşlukları tamamlamayı sever; eksik notları doldurmak öğrenmeyi hızlandırır.",
    "Aktif hatırlama (soru çözmek) pasif okumadan daha etkilidir.",
    "Huş ağacı kabuğu yüzyıllarca yazı malzemesi olarak kullanılmıştır.",
    "Öğrendikten 10 dakika sonra 2 dakikalık bir özet, hatırlamayı ciddi artırır.",
    "Farklı bağlamlarda aynı konuyu görmek, bilginin transferini kolaylaştırır.",
    "Quiz sırasında yanlış yapmak da öğrenmedir; hata, bir sonraki doğru cevabı güçlendirir.",
    "Bir konuyu birine anlatabiliyorsan, onu gerçekten anlamışsındır.",
    "Uyku sırasında beyin, gün içinde öğrendiklerini düzenler ve pekiştirir.",
    "Betula, kaynaklarındaki boşlukları bulup sentezleyerek çalışmanı tamamlar.",
  ];

  let tipTimer = null;
  let tipIndex = 0;

  function showNextTip() {
    const el = $("compile-tip");
    if (!el) return;
    tipIndex = (tipIndex + 1) % COMPILE_TIPS.length;
    el.style.animation = "none";
    void el.offsetWidth;
    el.style.animation = "";
    el.textContent = COMPILE_TIPS[tipIndex];
  }

  function startTips() {
    stopTips();
    tipIndex = Math.floor(Math.random() * COMPILE_TIPS.length);
    const el = $("compile-tip");
    if (el) el.textContent = COMPILE_TIPS[tipIndex];
    tipTimer = setInterval(showNextTip, 4500);
  }

  function stopTips() {
    if (tipTimer) clearInterval(tipTimer);
    tipTimer = null;
  }

  function showJob(status, step) {
    const badge = $("job-status");
    const overlay = $("compile-overlay");
    const title = $("compile-overlay-title");
    const msg = pipelineMessage(status, step);

    if (!status) {
      badge.classList.add("hidden");
      overlay.classList.add("hidden");
      stopTips();
      $("btn-compile").disabled = !state.selectedDocId;
      return;
    }

    const done = String(status).toLowerCase() === "done";
    const failed = String(status).toLowerCase() === "failed";

    badge.classList.remove("hidden");
    badge.textContent = msg;

    if (done || failed) {
      overlay.classList.add("hidden");
      stopTips();
      $("btn-compile").disabled = !state.selectedDocId;
      if (title) title.textContent = msg;
      return;
    }

    setView("notes");
    overlay.classList.remove("hidden");
    startTips();
    if (title && title.textContent !== msg) {
      title.style.animation = "none";
      void title.offsetWidth;
      title.style.animation = "";
      title.textContent = msg;
    } else if (title) {
      title.textContent = msg;
    }
    $("btn-compile").disabled = true;
  }

  function startPolling(jobId) {
    stopPolling();
    state.currentJobId = jobId;
    showJob("queued", "başlıyor");
    state.pollTimer = setInterval(async () => {
      try {
        const job = await LI.job(jobId);
        showJob(job.status, job.current_step);
        if (job.status === "done") {
          stopPolling();
          toast("Master sentez hazır");
          await loadDocuments();
          await loadCompiledNote(state.selectedDocId);
          showJob("done", "done");
          setTimeout(() => showJob(null), 2200);
        } else if (job.status === "failed") {
          stopPolling();
          toast(job.error || "Derleme başarısız");
          showJob("failed", "failed");
          setTimeout(() => showJob(null), 2800);
        }
      } catch (e) {
        stopPolling();
        showJob(null);
        toast(e.message);
      }
    }, 1500);
  }

  function stopPolling() {
    if (state.pollTimer) clearInterval(state.pollTimer);
    state.pollTimer = null;
  }

  async function uploadFile(file) {
    if (!file) return;
    toast(`Yükleniyor: ${file.name}`);
    try {
      const res = await LI.upload(file, true);
      toast("Yüklendi, derleme başladı");
      await loadDocuments();
      state.selectedDocId = res.document_id;
      renderSources();
      $("doc-title").textContent = res.filename;
      $("btn-compile").disabled = false;
      setView("notes");
      if (res.job?.id) startPolling(res.job.id);
      else await loadCompiledNote(res.document_id);
    } catch (e) {
      toast(e.message);
    }
  }

  function focusSourcesPanel() {
    showSidebarPanel("sources");
  }

  async function sendChat(text) {
    if (!text.trim()) return;
    appendChat("user", text);
    $("chat-input").value = "";
    const bodyEl = appendChat("assistant", "…");
    let assembled = "";
    let gotToken = false;
    try {
      const done = await LI.chatStream(
        {
          message: text,
          conversation_id: state.conversationId,
          document_id: state.selectedDocId,
          use_rag: true,
        },
        {
          onMeta: (meta) => {
            if (meta?.conversation_id) state.conversationId = meta.conversation_id;
          },
          onStatus: (msg) => {
            if (!gotToken) setChatBody(bodyEl, msg || "…");
          },
          onToken: (chunk) => {
            if (!gotToken) {
              gotToken = true;
              assembled = "";
            }
            assembled += chunk;
            setChatBody(bodyEl, assembled);
          },
          onError: (detail) => {
            if (!assembled) setChatBody(bodyEl, "Hata: " + detail);
          },
          onDone: async (payload) => {
            if (payload?.conversation_id) state.conversationId = payload.conversation_id;
            if (payload?.note_updated && state.selectedDocId) {
              toast("Yeni bilgi Master Sentez’e eklendi");
              setView("notes");
              await loadCompiledNote(state.selectedDocId);
            } else if (payload?.researched) {
              toast("Belgede yoktu — araştırılarak cevaplandı");
            }
            await loadConversations();
          },
        }
      );
      if (!assembled) setChatBody(bodyEl, "(Boş yanıt)");
      await loadConversations();
      return done;
    } catch (e) {
      setChatBody(bodyEl, "Hata: " + e.message);
    }
  }

  async function loadFlashcards() {
    const area = $("flashcard-area");
    try {
      state.flashcards = await LI.flashcardsReview(50, state.selectedDocId);
      $("fc-count").textContent = String(state.flashcards.length);
      state.flashIndex = 0;
      state.flashFlipped = false;
      renderFlashcard();
    } catch (e) {
      area.innerHTML = `<p class="text-sm text-error">${escapeHtml(e.message)}</p>`;
    }
  }

  function renderFlashcard() {
    const area = $("flashcard-area");
    const cards = state.flashcards;
    if (!cards.length) {
      area.innerHTML = `<p class="text-on-surface-variant text-sm">Kart yok. Üret butonunu kullan.</p>`;
      return;
    }
    const card = cards[state.flashIndex];
    area.innerHTML = `
      <div class="w-full max-w-lg">
        <p id="fc-progress" class="text-xs uppercase tracking-wider text-on-surface-variant mb-2">${state.flashIndex + 1} / ${cards.length} · ${state.flashFlipped ? "Cevap" : "Soru"} · tıkla çevir</p>
        <div class="fc-scene">
          <div id="fc-flip" class="fc-card${state.flashFlipped ? " is-flipped" : ""}" role="button" tabindex="0" aria-label="Kartı çevir">
            <div class="fc-face fc-face-front">
              <span class="fc-face-label">Soru</span>
              <p class="fc-face-text">${escapeHtml(card.question || "")}</p>
            </div>
            <div class="fc-face fc-face-back">
              <span class="fc-face-label">Cevap</span>
              <p class="fc-face-text">${escapeHtml(card.answer || "")}</p>
            </div>
          </div>
        </div>
        <div class="flex gap-3 mt-4">
          <button id="fc-prev" class="flex-1 py-2 rounded-lg border border-outline-variant text-sm" ${state.flashIndex === 0 ? "disabled" : ""}>Önceki</button>
          <button id="fc-next" class="flex-1 py-2 rounded-lg bg-primary text-on-primary text-sm">Sonraki</button>
        </div>
      </div>`;

    const flipEl = $("fc-flip");
    const progress = $("fc-progress");
    const toggleFlip = () => {
      state.flashFlipped = !state.flashFlipped;
      flipEl.classList.toggle("is-flipped", state.flashFlipped);
      if (progress) {
        progress.textContent = `${state.flashIndex + 1} / ${cards.length} · ${state.flashFlipped ? "Cevap" : "Soru"} · tıkla çevir`;
      }
    };
    flipEl.onclick = toggleFlip;
    flipEl.onkeydown = (e) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        toggleFlip();
      }
    };
    $("fc-prev").onclick = () => {
      if (state.flashIndex > 0) {
        state.flashIndex -= 1;
        state.flashFlipped = false;
        renderFlashcard();
      }
    };
    $("fc-next").onclick = () => {
      if (state.flashIndex < cards.length - 1) {
        state.flashIndex += 1;
        state.flashFlipped = false;
        renderFlashcard();
      } else {
        toast("Son kart");
      }
    };
  }

  async function generateFlashcards() {
    if (!state.selectedDocId) return toast("Önce bir kaynak seç");
    toast("Flashcard üretiliyor…");
    try {
      const res = await LI.flashcardsGenerate(state.selectedDocId, 10);
      toast(`${res.created} kart oluşturuldu`);
      await loadFlashcards();
    } catch (e) {
      toast(e.message);
    }
  }

  function startQuizFlow() {
    renderQuizSetup();
  }

  function renderQuizSetup() {
    const area = $("quiz-area");
    if (!state.selectedDocId) {
      area.innerHTML = `<p class="text-sm text-on-surface-variant">Önce bir kaynak seç, sonra quiz oluştur.</p>`;
      return;
    }
    const doc = state.documents.find((d) => d.id === state.selectedDocId);
    const counts = [5, 10, 15];
    area.innerHTML = `
      <div class="max-w-lg mx-auto">
        <h3 class="text-[18px] font-semibold text-on-surface mb-1">Yeni Quiz Oluştur</h3>
        <p class="text-sm text-on-surface-variant mb-6">Kaynak: ${escapeHtml(doc?.filename || "#" + state.selectedDocId)}</p>

        <label class="block text-[13px] font-medium text-on-surface mb-2">Konu (opsiyonel)</label>
        <input id="quiz-topic" type="text" value="${escapeAttr(state.quizTopic || "")}"
          placeholder="Örn. hücre bölünmesi — boş bırakırsan tüm kaynaktan"
          class="w-full mb-5 px-4 py-2.5 rounded-lg border border-outline-variant bg-surface-container-lowest text-sm text-on-surface outline-none focus:border-primary"/>

        <label class="block text-[13px] font-medium text-on-surface mb-2">Soru sayısı</label>
        <div class="flex gap-2 mb-7" id="quiz-count-group">
          ${counts
            .map(
              (c) =>
                `<button data-count="${c}" class="quiz-count-btn flex-1 py-2.5 rounded-lg border text-sm font-medium transition-colors ${
                  state.quizCount === c
                    ? "border-primary bg-primary text-on-primary"
                    : "border-outline-variant bg-surface-container-lowest text-on-surface hover:border-primary"
                }">${c}</button>`
            )
            .join("")}
        </div>

        <button id="quiz-generate-btn" class="w-full py-3 rounded-lg bg-primary text-on-primary text-sm font-semibold hover:opacity-90 transition-opacity">
          Üret & Başlat
        </button>
        <p class="text-[12px] text-on-surface-variant mt-3">Sadece çoktan seçmeli ve doğru/yanlış. Arşivlenen sorular tekrar gelmez; yarım kalan quiz soruları yeniden sorulabilir.</p>
      </div>`;

    area.querySelectorAll(".quiz-count-btn").forEach((btn) => {
      btn.onclick = () => {
        state.quizCount = Number(btn.dataset.count);
        renderQuizSetup();
      };
    });
    $("quiz-generate-btn").onclick = generateQuiz;
    const topicEl = $("quiz-topic");
    topicEl.oninput = () => {
      state.quizTopic = topicEl.value;
    };
  }

  function showQuizGrowing() {
    const area = $("quiz-area");
    const letters = "Betula"
      .split("")
      .map((c) => `<span class="ch">${c}</span>`)
      .join("");
    area.innerHTML = `
      <div class="quiz-grow" aria-live="polite" aria-busy="true">
        <div class="quiz-grow-stage">
          <div class="quiz-grow-word" aria-label="Betula">${letters}</div>
          <div class="quiz-grow-logo">
            <span class="material-symbols-outlined" style="font-variation-settings:'FILL' 1;font-size:48px;color:#d95d39" aria-hidden="true">eco</span>
          </div>
        </div>
        <p class="quiz-grow-label">Quiz üretiliyor<span class="quiz-grow-dots"><span>.</span><span>.</span><span>.</span></span></p>
      </div>`;
  }

  async function generateQuiz() {
    if (!state.selectedDocId) return toast("Önce bir kaynak seç");
    const topicEl = $("quiz-topic");
    if (topicEl) state.quizTopic = topicEl.value.trim();
    showQuizGrowing();
    try {
      const res = await LI.quizGenerate(state.selectedDocId, state.quizCount, state.quizTopic || null);
      if (!res.questions || !res.questions.length) {
        toast("Soru üretilemedi, tekrar dene");
        renderQuizSetup();
        return;
      }
      state.quiz = res.questions;
      state.quizIndex = 0;
      state.quizAnswers = [];
      renderQuiz();
    } catch (e) {
      toast(e.message);
      renderQuizSetup();
    }
  }

  function renderQuiz() {
    const area = $("quiz-area");
    const q = state.quiz[state.quizIndex];
    if (!q) {
      finishQuiz();
      return;
    }
    const options = q.options || [];
    const typeLabel = q.question_type === "true_false" ? "Doğru / Yanlış" : "Çoktan seçmeli";
    area.innerHTML = `
      <div class="max-w-xl mx-auto">
        <div class="flex items-center justify-between mb-2">
          <p class="text-xs uppercase tracking-wider text-on-surface-variant">Soru ${state.quizIndex + 1} / ${state.quiz.length}</p>
          <span class="text-[11px] px-2 py-0.5 rounded-full bg-surface-container text-on-surface-variant border border-outline-variant">${typeLabel}</span>
        </div>
        <h3 class="text-[16px] font-semibold text-on-surface mb-4">${escapeHtml(q.question_text || "")}</h3>
        <div class="flex flex-col gap-2" id="quiz-options">
          ${options
            .map(
              (o) =>
                `<button data-answer="${escapeAttr(o)}" class="quiz-opt text-left px-4 py-3 rounded-lg border border-outline-variant hover:border-primary bg-surface-container-lowest text-sm text-on-surface transition-colors">${escapeHtml(o)}</button>`
            )
            .join("")}
        </div>
        <div id="quiz-feedback" class="mt-4 hidden"></div>
      </div>`;
    area.querySelectorAll(".quiz-opt").forEach((btn) => {
      btn.onclick = () => answerQuiz(btn.dataset.answer, btn);
    });
  }

  function lockQuizOptions() {
    document.querySelectorAll(".quiz-opt").forEach((btn) => {
      btn.disabled = true;
      btn.classList.add("cursor-default");
      btn.onclick = null;
    });
  }

  async function answerQuiz(answer, clickedBtn) {
    const q = state.quiz[state.quizIndex];
    const fb = $("quiz-feedback");
    if (!fb || fb.dataset.answered === "1") return;
    try {
      const res = await LI.quizAnswer(q.id, answer);
      lockQuizOptions();
      fb.dataset.answered = "1";
      fb.classList.remove("hidden");

      // Tüm seçenekleri renklendir: doğru yeşil, seçilen yanlışsa kırmızı
      document.querySelectorAll(".quiz-opt").forEach((btn) => {
        const val = btn.dataset.answer;
        if (val === res.correct_answer) {
          btn.classList.remove("border-outline-variant");
          btn.classList.add("border-green-600", "bg-green-50");
        }
      });
      if (clickedBtn && !res.correct) {
        clickedBtn.classList.remove("border-outline-variant");
        clickedBtn.classList.add("border-red-600", "bg-red-50");
      }

      state.quizAnswers.push({ question_id: q.id, given_answer: answer });

      const statusColor = res.correct ? "text-green-700" : "text-red-700";
      const statusText = res.correct ? "Doğru" : "Yanlış";
      const isLast = state.quizIndex >= state.quiz.length - 1;
      const nextLabel = isLast ? "Bitir & Sonuç" : "Sonraki soru";

      fb.innerHTML = `
        <p class="text-[15px] font-semibold ${statusColor} mb-2">${statusText}</p>
        <p class="text-sm text-on-surface mb-1"><span class="font-medium">Doğru cevap:</span> ${escapeHtml(res.correct_answer || "")}</p>
        ${res.explanation ? `<p class="text-sm text-on-surface-variant mb-3">${escapeHtml(res.explanation)}</p>` : `<div class="mb-3"></div>`}
        <button id="quiz-next" class="px-4 py-2 rounded-lg bg-primary text-on-primary text-sm">${nextLabel}</button>
      `;
      $("quiz-next").onclick = () => {
        state.quizIndex += 1;
        renderQuiz();
      };
    } catch (e) {
      toast(e.message);
    }
  }

  async function finishQuiz() {
    const area = $("quiz-area");
    area.innerHTML = `<p class="text-sm text-on-surface-variant">Sonuç kaydediliyor…</p>`;
    try {
      const result = await LI.quizAttemptCreate({
        document_id: state.selectedDocId,
        topic: state.quizTopic || null,
        answers: state.quizAnswers,
      });
      renderQuizResult(result);
      LI.stats()
        .then((s) => {
          if (s?.total_flashcards != null) $("fc-count").textContent = String(s.total_flashcards);
        })
        .catch(() => {});
    } catch (e) {
      area.innerHTML = `<p class="text-sm text-error">${escapeHtml(e.message)}</p>
        <button id="quiz-retry" class="mt-3 px-4 py-2 rounded-lg bg-primary text-on-primary text-sm">Yeni Quiz</button>`;
      $("quiz-retry").onclick = renderQuizSetup;
    }
  }

  function renderQuizResult(result) {
    const area = $("quiz-area");
    const pct = result.score_pct ?? 0;
    const color = pct >= 70 ? "text-green-700" : pct >= 40 ? "text-amber-600" : "text-red-700";
    area.innerHTML = `
      <div class="max-w-lg mx-auto text-center">
        <h3 class="text-[18px] font-semibold text-on-surface mb-6">Quiz Tamamlandı</h3>
        <div class="inline-flex flex-col items-center justify-center w-40 h-40 rounded-full border-4 border-outline-variant mb-6">
          <span class="text-[38px] font-bold ${color}">%${pct}</span>
          <span class="text-sm text-on-surface-variant mt-1">${result.correct_count} / ${result.total_questions} doğru</span>
        </div>
        <div class="flex gap-3 justify-center">
          <button id="quiz-again" class="px-5 py-2.5 rounded-lg bg-primary text-on-primary text-sm font-semibold">Yeni Quiz</button>
          <button id="quiz-see-archive" class="px-5 py-2.5 rounded-lg border border-outline-variant text-on-surface text-sm">Arşivi Gör</button>
        </div>
      </div>`;
    $("quiz-again").onclick = renderQuizSetup;
    $("quiz-see-archive").onclick = renderQuizArchive;
  }

  async function renderQuizArchive() {
    const area = $("quiz-area");
    area.innerHTML = `<p class="text-sm text-on-surface-variant">Arşiv yükleniyor…</p>`;
    try {
      const attempts = await LI.quizAttempts();
      if (!attempts.length) {
        area.innerHTML = `
          <div class="max-w-lg mx-auto text-center">
            <p class="text-sm text-on-surface-variant mb-4">Henüz çözülmüş quiz yok.</p>
            <button id="quiz-archive-new" class="px-5 py-2.5 rounded-lg bg-primary text-on-primary text-sm font-semibold">Yeni Quiz</button>
          </div>`;
        $("quiz-archive-new").onclick = renderQuizSetup;
        return;
      }
      area.innerHTML = `
        <div class="max-w-2xl mx-auto">
          <div class="flex items-center justify-between mb-4">
            <h3 class="text-[16px] font-semibold text-on-surface">Quiz Arşivi</h3>
            <button id="quiz-archive-new" class="text-xs uppercase tracking-wider px-3 py-1 rounded-full bg-primary text-on-primary">Yeni Quiz</button>
          </div>
          <ul class="flex flex-col gap-2">
            ${attempts
              .map((a) => {
                const pct = a.score_pct ?? 0;
                const color = pct >= 70 ? "text-green-700" : pct >= 40 ? "text-amber-600" : "text-red-700";
                return `
                <li>
                  <button data-attempt="${a.id}" class="quiz-attempt-btn w-full text-left p-3 rounded-lg border border-outline-variant bg-surface-container-lowest hover:border-primary transition-colors flex items-center justify-between gap-3">
                    <span class="min-w-0">
                      <span class="block text-[14px] font-medium text-on-surface truncate">${escapeHtml(a.topic || a.filename || "Genel")}</span>
                      <span class="block text-[12px] text-on-surface-variant">${formatDate(a.created_at)} · ${a.total_questions} soru</span>
                    </span>
                    <span class="text-[15px] font-bold ${color} shrink-0">%${pct}</span>
                  </button>
                </li>`;
              })
              .join("")}
          </ul>
        </div>`;
      $("quiz-archive-new").onclick = renderQuizSetup;
      area.querySelectorAll(".quiz-attempt-btn").forEach((btn) => {
        btn.onclick = () => renderAttemptDetail(Number(btn.dataset.attempt));
      });
    } catch (e) {
      area.innerHTML = `<p class="text-sm text-error">${escapeHtml(e.message)}</p>`;
    }
  }

  async function renderAttemptDetail(attemptId) {
    const area = $("quiz-area");
    area.innerHTML = `<p class="text-sm text-on-surface-variant">Yükleniyor…</p>`;
    try {
      const a = await LI.quizAttempt(attemptId);
      const pct = a.score_pct ?? 0;
      const color = pct >= 70 ? "text-green-700" : pct >= 40 ? "text-amber-600" : "text-red-700";
      area.innerHTML = `
        <div class="max-w-2xl mx-auto">
          <button id="quiz-back-archive" class="text-[13px] text-primary hover:underline mb-4 flex items-center gap-1">
            <span class="material-symbols-outlined text-[16px]">arrow_back</span> Arşive dön
          </button>
          <div class="flex items-center justify-between mb-5">
            <div>
              <h3 class="text-[16px] font-semibold text-on-surface">${escapeHtml(a.topic || a.filename || "Genel")}</h3>
              <p class="text-[12px] text-on-surface-variant">${formatDate(a.created_at)}</p>
            </div>
            <span class="text-[18px] font-bold ${color}">%${pct} · ${a.correct_count}/${a.total_questions}</span>
          </div>
          <ol class="flex flex-col gap-3">
            ${a.items
              .map((it, i) => {
                const ok = it.is_correct;
                const badge = ok
                  ? `<span class="text-[12px] font-semibold text-green-700">Doğru</span>`
                  : `<span class="text-[12px] font-semibold text-red-700">Yanlış</span>`;
                const givenLine = ok
                  ? ""
                  : `<p class="text-[13px] text-red-700 mt-1"><span class="font-medium">Senin cevabın:</span> ${escapeHtml(it.given_answer || "—")}</p>`;
                return `
                <li class="p-3 rounded-lg border border-outline-variant bg-surface-container-lowest">
                  <div class="flex items-start justify-between gap-2">
                    <p class="text-[14px] font-medium text-on-surface">${i + 1}. ${escapeHtml(it.question_text || "")}</p>
                    ${badge}
                  </div>
                  <p class="text-[13px] text-green-700 mt-1"><span class="font-medium">Doğru cevap:</span> ${escapeHtml(it.correct_answer || "")}</p>
                  ${givenLine}
                  ${it.explanation ? `<p class="text-[13px] text-on-surface-variant mt-1">${escapeHtml(it.explanation)}</p>` : ""}
                </li>`;
              })
              .join("")}
          </ol>
        </div>`;
      $("quiz-back-archive").onclick = renderQuizArchive;
    } catch (e) {
      area.innerHTML = `<p class="text-sm text-error">${escapeHtml(e.message)}</p>`;
    }
  }

  function escapeHtml(s) {
    return String(s ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }
  function escapeAttr(s) {
    return escapeHtml(s).replace(/'/g, "&#39;");
  }
  function formatDate(d) {
    if (!d) return "";
    try {
      // SQLite CURRENT_TIMESTAMP UTC (naive) → GMT+3 (Europe/Istanbul)
      const raw = String(d).trim().replace(" ", "T");
      const iso = /Z$|[+-]\d{2}:?\d{2}$/.test(raw) ? raw : `${raw}Z`;
      return new Date(iso).toLocaleString("tr-TR", {
        timeZone: "Europe/Istanbul",
        dateStyle: "short",
        timeStyle: "short",
      });
    } catch {
      return String(d);
    }
  }

  // Events
  $("btn-logout").onclick = () => {
    if (window.ProfileMenu?.confirmLogout) ProfileMenu.confirmLogout();
    else {
      Auth.clear();
      location.href = "/";
    }
  };

  // Sol panel: kapat/aç + genişlik kaydırma
  (function initSidebarChrome() {
    const sidebar = $("app-sidebar");
    const main = $("app-main");
    const toggle = $("sidebar-toggle");
    const icon = $("sidebar-toggle-icon");
    const resizer = $("sidebar-resizer");
    if (!sidebar || !main || !toggle) return;

    const KEY_W = "betula_sidebar_w";
    const KEY_C = "betula_sidebar_collapsed";
    const MAX = 256;

    function measureMinWidth() {
      const labels = sidebar.querySelectorAll("#nav-main .nav-btn .font-label-sm, #btn-new-upload");
      let maxLabel = 120;
      labels.forEach((el) => {
        maxLabel = Math.max(maxLabel, el.scrollWidth || 0);
      });
      // ikon (24) + gap + padding yatay (~48) + badge payı
      const min = Math.ceil(maxLabel + 24 + 12 + 48 + 28);
      return Math.min(MAX, Math.max(188, min));
    }

    let minW = measureMinWidth();
    document.documentElement.style.setProperty("--sidebar-min", `${minW}px`);
    document.documentElement.style.setProperty("--sidebar-max", `${MAX}px`);

    let width = Number(localStorage.getItem(KEY_W)) || MAX;
    width = Math.min(MAX, Math.max(minW, width));
    let collapsed = localStorage.getItem(KEY_C) === "1";

    function apply() {
      minW = measureMinWidth();
      document.documentElement.style.setProperty("--sidebar-min", `${minW}px`);
      width = Math.min(MAX, Math.max(minW, width));
      const shown = collapsed ? 0 : width;
      document.documentElement.style.setProperty("--sidebar-w", `${shown}px`);
      sidebar.classList.toggle("is-collapsed", collapsed);
      main.classList.toggle("is-sidebar-collapsed", collapsed);
      toggle.classList.toggle("is-collapsed", collapsed);
      if (icon) icon.textContent = collapsed ? "chevron_right" : "chevron_left";
      toggle.title = collapsed ? "Sol paneli aç" : "Sol paneli kapat";
      localStorage.setItem(KEY_W, String(width));
      localStorage.setItem(KEY_C, collapsed ? "1" : "0");
    }

    apply();

    toggle.addEventListener("click", () => {
      collapsed = !collapsed;
      apply();
    });

    if (resizer) {
      let dragging = false;
      const onMove = (e) => {
        if (!dragging || collapsed) return;
        const x = e.touches ? e.touches[0].clientX : e.clientX;
        width = Math.min(MAX, Math.max(minW, x));
        document.documentElement.style.setProperty("--sidebar-w", `${width}px`);
      };
      const onUp = () => {
        if (!dragging) return;
        dragging = false;
        sidebar.classList.remove("is-resizing");
        main.classList.remove("is-resizing");
        document.body.style.cursor = "";
        document.body.style.userSelect = "";
        window.removeEventListener("pointermove", onMove);
        window.removeEventListener("pointerup", onUp);
        window.removeEventListener("touchmove", onMove);
        window.removeEventListener("touchend", onUp);
        apply();
      };
      const onDown = (e) => {
        if (collapsed) return;
        e.preventDefault();
        dragging = true;
        sidebar.classList.add("is-resizing");
        main.classList.add("is-resizing");
        document.body.style.cursor = "col-resize";
        document.body.style.userSelect = "none";
        window.addEventListener("pointermove", onMove);
        window.addEventListener("pointerup", onUp);
        window.addEventListener("touchmove", onMove, { passive: false });
        window.addEventListener("touchend", onUp);
      };
      resizer.addEventListener("pointerdown", onDown);
      resizer.addEventListener("touchstart", onDown, { passive: false });
    }

    window.addEventListener("resize", () => {
      minW = measureMinWidth();
      apply();
    });
  })();

  (function initMasterPanel() {
    const panel = $("master-panel");
    const main = $("app-main");
    const toggle = $("master-toggle");
    const icon = $("master-toggle-icon");
    const resizer = $("master-resizer");
    if (!panel || !toggle || !main) return;

    const KEY_W = "betula_master_w";
    const KEY_C = "betula_master_collapsed";
    const MIN = 260;
    const MAX = 420;

    let width = Number(localStorage.getItem(KEY_W)) || 320;
    width = Math.min(MAX, Math.max(MIN, width));
    let collapsed = localStorage.getItem(KEY_C) === "1";

    function apply() {
      width = Math.min(MAX, Math.max(MIN, width));
      // Açık genişlik her zaman ayrı tutulur; margin sınıf ile sıfırlanır
      document.documentElement.style.setProperty("--master-panel-w", `${width}px`);
      document.documentElement.style.setProperty("--master-w", collapsed ? "0px" : `${width}px`);
      panel.classList.toggle("is-collapsed", collapsed);
      main.classList.toggle("is-master-collapsed", collapsed);
      toggle.classList.toggle("is-collapsed", collapsed);
      if (icon) icon.textContent = collapsed ? "chevron_left" : "chevron_right";
      toggle.title = collapsed ? "Master Sentez’i aç" : "Master Sentez’i kapat";
      localStorage.setItem(KEY_W, String(width));
      localStorage.setItem(KEY_C, collapsed ? "1" : "0");
    }

    apply();

    toggle.addEventListener("click", () => {
      collapsed = !collapsed;
      apply();
    });

    if (resizer) {
      let dragging = false;
      const onMove = (e) => {
        if (!dragging || collapsed) return;
        const x = e.touches ? e.touches[0].clientX : e.clientX;
        width = Math.min(MAX, Math.max(MIN, window.innerWidth - x));
        document.documentElement.style.setProperty("--master-panel-w", `${width}px`);
        document.documentElement.style.setProperty("--master-w", `${width}px`);
      };
      const onUp = () => {
        if (!dragging) return;
        dragging = false;
        panel.classList.remove("is-resizing");
        main.classList.remove("is-resizing");
        document.body.style.cursor = "";
        document.body.style.userSelect = "";
        window.removeEventListener("pointermove", onMove);
        window.removeEventListener("pointerup", onUp);
        window.removeEventListener("touchmove", onMove);
        window.removeEventListener("touchend", onUp);
        apply();
      };
      const onDown = (e) => {
        if (collapsed) return;
        e.preventDefault();
        dragging = true;
        panel.classList.add("is-resizing");
        main.classList.add("is-resizing");
        document.body.style.cursor = "col-resize";
        document.body.style.userSelect = "none";
        window.addEventListener("pointermove", onMove);
        window.addEventListener("pointerup", onUp);
        window.addEventListener("touchmove", onMove, { passive: false });
        window.addEventListener("touchend", onUp);
      };
      resizer.addEventListener("pointerdown", onDown);
      resizer.addEventListener("touchstart", onDown, { passive: false });
    }
  })();

  $("btn-new-upload").onclick = () => $("file-input").click();
  $("btn-add-source").onclick = () => $("file-input").click();
  $("file-input").onchange = (e) => uploadFile(e.target.files?.[0]);
  $("btn-compile").onclick = async () => {
    if (!state.selectedDocId) return;
    try {
      const job = await LI.compile(state.selectedDocId);
      toast("Derleme başladı");
      startPolling(job.id);
    } catch (e) {
      toast(e.message);
    }
  };
  $("chat-form").onsubmit = (e) => {
    e.preventDefault();
    sendChat($("chat-input").value);
  };
  $("btn-gen-cards").onclick = generateFlashcards;
  $("btn-quiz-new").onclick = renderQuizSetup;
  $("btn-quiz-archive").onclick = renderQuizArchive;

  document.querySelectorAll("[data-close-study]").forEach((el) => {
    el.addEventListener("click", () => {
      closeStudyModals();
      setView("notes");
    });
  });
  document.addEventListener("keydown", (e) => {
    if (e.key !== "Escape") return;
    const fcOpen = !$("modal-flashcards")?.classList.contains("is-hidden");
    const quizOpen = !$("modal-quiz")?.classList.contains("is-hidden");
    if (fcOpen || quizOpen) {
      closeStudyModals();
      setView("notes");
    }
  });

  document.querySelectorAll(".nav-btn[data-view], .tool-btn[data-view]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const v = btn.dataset.view;
      if (!v) return;
      showSidebarPanel("main");
      setView(v);
    });
  });

  $("btn-open-sources")?.addEventListener("click", () => {
    showSidebarPanel("sources");
  });
  $("btn-sources-back")?.addEventListener("click", () => {
    showSidebarPanel("main");
  });

  if (Auth.user) {
    $("session-label").textContent = "…";
  }
  if (window.ProfileMenu) ProfileMenu.mount();
  LI.sessionGet(Auth.sessionId)
    .then((s) => {
      if (s?.title) $("session-label").textContent = s.title;
    })
    .catch(() => {
      $("session-label").textContent = Auth.user?.name || "Oturum";
    });

  $("btn-export-note")?.addEventListener("click", (e) => {
    e.stopPropagation();
    $("export-master-menu")?.classList.add("hidden");
    $("export-note-menu")?.classList.toggle("hidden");
  });
  $("btn-download-note")?.addEventListener("click", (e) => {
    e.stopPropagation();
    $("export-note-menu")?.classList.add("hidden");
    $("export-master-menu")?.classList.toggle("hidden");
  });
  document.querySelectorAll("[data-export-note]").forEach((btn) => {
    btn.addEventListener("click", () => exportCurrent("note", btn.getAttribute("data-export-note")));
  });
  document.querySelectorAll("[data-export-master]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const [kind, format] = (btn.getAttribute("data-export-master") || "note:docx").split(":");
      exportCurrent(kind, format);
    });
  });
  document.addEventListener("click", () => closeExportMenus());

  // Hash deep-links
  const hash = (location.hash || "").replace("#", "");
  if (["flashcards", "quiz", "notes"].includes(hash)) setView(hash);
  else setView("notes");

  (async () => {
    try {
      await loadDocuments();
      await loadConversations();
      const stats = await LI.stats().catch(() => null);
      if (stats?.total_flashcards != null) $("fc-count").textContent = String(stats.total_flashcards);
    } catch (e) {
      if (e.status === 401) {
        Auth.clear();
        location.href = "/?login=1";
      } else toast(e.message);
    }
  })();
})();
