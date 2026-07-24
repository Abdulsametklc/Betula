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

  function setView(view) {
    const notes = $("panel-notes");
    const fc = $("panel-flashcards");
    const quiz = $("panel-quiz");
    notes.classList.add("panel-hidden");
    fc.classList.add("panel-hidden");
    quiz.classList.add("panel-hidden");
    if (view === "flashcards") fc.classList.remove("panel-hidden");
    else if (view === "quiz") quiz.classList.remove("panel-hidden");
    else notes.classList.remove("panel-hidden");

    document.querySelectorAll(".nav-btn").forEach((btn) => {
      const active = btn.dataset.view === view || (view === "notes" && btn.dataset.view === "notes") || (view === "sources" && btn.dataset.view === "sources") || (view === "history" && btn.dataset.view === "history");
      btn.classList.toggle("nav-active", active && ["notes", "flashcards", "quiz"].includes(btn.dataset.view));
      if (!["notes", "flashcards", "quiz"].includes(btn.dataset.view)) {
        btn.classList.remove("nav-active");
      }
    });

    if (view === "flashcards") loadFlashcards();
    if (view === "quiz") startQuizFlow();
    if (view === "history") loadConversations();
  }

  function renderSources() {
    const list = $("sources-list");
    if (!state.documents.length) {
      list.innerHTML = `<p class="text-sm text-on-surface-variant">Henüz kaynak yok. PDF/DOCX yükle.</p>`;
      return;
    }
    list.innerHTML = state.documents
      .map((d) => {
        const active = d.id === state.selectedDocId;
        const iconBg = d.doc_type === "pdf" ? "bg-error-container text-on-error-container" : "bg-primary-container text-on-primary-container";
        const icon = d.doc_type === "pdf" ? "picture_as_pdf" : "description";
        return `
        <button data-doc-id="${d.id}" class="source-item glass-card p-3 rounded-lg flex items-start gap-3 text-left w-full transition-all ${active ? "border-primary" : "hover:border-primary"} bg-surface-container-lowest">
          <div class="w-8 h-8 rounded ${iconBg} flex items-center justify-center shrink-0">
            <span class="material-symbols-outlined text-[16px]" style="font-variation-settings: 'FILL' 1;">${icon}</span>
          </div>
          <div class="overflow-hidden">
            <h3 class="text-[14px] font-medium truncate text-on-surface">${escapeHtml(d.filename)}</h3>
            <p class="text-[12px] text-on-surface-variant truncate mt-1">${d.is_processed ? "İşlendi" : "Bekliyor"} · ${formatDate(d.upload_date)}</p>
          </div>
        </button>`;
      })
      .join("");

    list.querySelectorAll("[data-doc-id]").forEach((btn) => {
      btn.addEventListener("click", () => selectDocument(Number(btn.dataset.docId)));
    });
  }

  function renderHistory() {
    const list = $("history-list");
    if (!state.conversations.length) {
      list.innerHTML = `<p class="text-sm text-on-surface-variant">Sohbet yok.</p>`;
      return;
    }
    list.innerHTML = state.conversations
      .map(
        (c) => `
      <button data-conv-id="${c.id}" class="text-[13px] text-left text-on-surface hover:text-primary cursor-pointer transition-colors truncate pb-2 border-b border-outline-variant w-full">
        ${escapeHtml(c.title || "Sohbet")}
      </button>`
      )
      .join("");
    list.querySelectorAll("[data-conv-id]").forEach((btn) => {
      btn.addEventListener("click", () => openConversation(Number(btn.dataset.convId)));
    });
  }

  function appendChat(role, content) {
    const box = $("chat-messages");
    const isUser = role === "user";
    const wrap = document.createElement("div");
    wrap.className = isUser
      ? "flex items-start gap-3 self-end flex-row-reverse max-w-[85%]"
      : "flex items-start gap-3 max-w-[92%]";
    wrap.innerHTML = `
      <div class="w-8 h-8 rounded-full ${isUser ? "bg-surface-container" : "bg-primary-container text-on-primary-container border border-outline-variant"} flex items-center justify-center shrink-0">
        <span class="material-symbols-outlined text-[16px]">${isUser ? "person" : "robot_2"}</span>
      </div>
      <div data-chat-body class="${isUser ? "bg-surface-container rounded-tr-none" : "bg-surface-container rounded-tl-none"} p-3 rounded-lg text-[14px] leading-relaxed text-on-surface border border-outline-variant whitespace-pre-wrap">${escapeHtml(content)}</div>`;
    box.appendChild(wrap);
    box.scrollTop = box.scrollHeight;
    return wrap.querySelector("[data-chat-body]");
  }

  function setChatBody(el, content) {
    if (!el) return;
    el.textContent = content;
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

  async function loadConversations() {
    state.conversations = await LI.conversations();
    renderHistory();
  }

  async function selectDocument(id) {
    state.selectedDocId = id;
    renderSources();
    const doc = state.documents.find((d) => d.id === id);
    $("doc-title").textContent = doc?.filename || `Doküman #${id}`;
    $("btn-compile").disabled = false;
    setView("notes");
    await loadCompiledNote(id);
  }

  async function loadCompiledNote(docId) {
    const noteBox = $("note-content");
    const gaps = $("gap-list");
    const dl = $("btn-download-note");
    try {
      const note = await LI.compiledNote(docId);
      const html = typeof marked !== "undefined" ? marked.parse(note.markdown || "") : escapeHtml(note.markdown || "");
      noteBox.innerHTML = `<div class="max-w-3xl mx-auto bg-surface-container-lowest border border-outline-variant rounded-lg p-8 shadow-md prose-note">${html}</div>`;
      renderGaps(note.gap_list || []);
      dl.classList.remove("hidden");
      dl.href = `${API_BASE}/documents/${docId}/compiled-note/download`;
      dl.onclick = (e) => {
        e.preventDefault();
        fetch(dl.href, { headers: { Authorization: `Bearer ${Auth.token}` } })
          .then((r) => r.blob())
          .then((blob) => {
            const a = document.createElement("a");
            a.href = URL.createObjectURL(blob);
            a.download = `compiled_note_${docId}.md`;
            a.click();
          });
      };
    } catch {
      noteBox.innerHTML = `<div class="max-w-3xl mx-auto bg-surface-container-lowest border border-outline-variant rounded-lg p-8 shadow-md prose-note">
        <h2 class="text-[22px] font-semibold mb-3">Derlenmiş not yok</h2>
        <p class="text-on-surface-variant mb-4">Bu kaynak henüz işlenmedi. “Derle” ile araştırma boru hattını başlat.</p>
      </div>`;
      gaps.innerHTML = `<li class="text-sm text-on-surface-variant">Henüz gap yok.</li>`;
      dl.classList.add("hidden");
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
              <span class="block text-[13px] font-semibold text-on-surface">${escapeHtml(g.topic || "Konu")}</span>
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

  async function openConversation(id) {
    state.conversationId = id;
    clearChat();
    const msgs = await LI.messages(id);
    msgs.forEach((m) => appendChat(m.role, m.content));
    setView("notes");
  }

  async function sendChat(text) {
    if (!text.trim()) return;
    appendChat("user", text);
    $("chat-input").value = "";
    const bodyEl = appendChat("assistant", "…");
    let assembled = "";
    try {
      await LI.chatStream(
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
          onToken: (chunk) => {
            assembled += chunk;
            setChatBody(bodyEl, assembled);
          },
          onError: (detail) => {
            if (!assembled) setChatBody(bodyEl, "Hata: " + detail);
          },
        }
      );
      if (!assembled) setChatBody(bodyEl, "(Boş yanıt)");
      await loadConversations();
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
    const side = state.flashFlipped ? card.answer : card.question;
    area.innerHTML = `
      <div class="w-full max-w-lg">
        <p class="text-xs uppercase tracking-wider text-on-surface-variant mb-2">${state.flashIndex + 1} / ${cards.length} · ${state.flashFlipped ? "Cevap" : "Soru"}</p>
        <button id="fc-flip" class="w-full min-h-[180px] p-6 rounded-xl border border-outline-variant bg-surface-container-lowest text-left hover:border-primary transition-colors">
          <p class="text-[16px] text-on-surface whitespace-pre-wrap">${escapeHtml(side)}</p>
        </button>
        <div class="flex gap-3 mt-4">
          <button id="fc-prev" class="flex-1 py-2 rounded-lg border border-outline-variant text-sm" ${state.flashIndex === 0 ? "disabled" : ""}>Önceki</button>
          <button id="fc-next" class="flex-1 py-2 rounded-lg bg-primary text-on-primary text-sm">Sonraki</button>
        </div>
      </div>`;
    $("fc-flip").onclick = () => {
      state.flashFlipped = !state.flashFlipped;
      renderFlashcard();
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
            <img src="/static/assets/betula-logo.png" alt=""/>
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
      return new Date(d).toLocaleString("tr-TR", { dateStyle: "short", timeStyle: "short" });
    } catch {
      return String(d);
    }
  }

  // Events
  $("btn-logout").onclick = () => {
    Auth.clear();
    location.href = "/";
  };
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

  document.querySelectorAll(".nav-btn, .tool-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      const v = btn.dataset.view;
      if (v === "sources") {
        setView("notes");
        $("btn-add-source")?.focus();
      } else if (v === "history") {
        setView("notes");
        loadConversations();
      } else if (v) setView(v);
    });
  });

  if (Auth.user) {
    $("session-label").textContent = "…";
  }
  LI.sessionGet(Auth.sessionId)
    .then((s) => {
      if (s?.title) $("session-label").textContent = s.title;
    })
    .catch(() => {
      $("session-label").textContent = Auth.user?.name || "Oturum";
    });

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
