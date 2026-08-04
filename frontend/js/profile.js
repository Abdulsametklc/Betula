/**
 * Ortak profil avatar menüsü — sağ üst avatar tıklanınca açılır.
 * Beklenen: #profile-avatar-btn (ve isteğe bağlı #profile-avatar-host)
 */
(function () {
  const ICON_FALLBACK = [
    "person",
    "face",
    "school",
    "psychology",
    "menu_book",
    "lightbulb",
    "science",
    "biotech",
    "pets",
    "favorite",
    "star",
    "bolt",
    "palette",
    "music_note",
    "sports_esports",
    "travel_explore",
  ];

  function paintAvatar(el, user) {
    if (!el) return;
    const u = user || Auth.user || {};
    el.innerHTML = "";
    el.classList.remove("overflow-hidden");

    if (u.avatar_type === "image" && u.avatar_value) {
      el.classList.add("overflow-hidden");
      const img = document.createElement("img");
      img.src = Auth.avatarSrc(u);
      img.alt = "Profil";
      img.className = "w-full h-full object-cover";
      img.onerror = () => {
        el.innerHTML = "";
        el.textContent = Auth.initial();
      };
      el.appendChild(img);
      return;
    }
    if (u.avatar_type === "icon" && u.avatar_value) {
      const span = document.createElement("span");
      span.className = "material-symbols-outlined text-[22px]";
      span.style.fontVariationSettings = "'FILL' 1";
      span.textContent = u.avatar_value;
      el.appendChild(span);
      return;
    }
    el.textContent = Auth.initial();
  }

  const ROOT_SVG = `
    <svg class="profile-root-svg" viewBox="0 0 100 100" aria-hidden="true">
      <circle class="root-ring" cx="50" cy="50" r="36"/>
      <path class="root-stroke" d="M18 52 C 10 40, 14 24, 28 18 C 22 28, 20 40, 24 48"/>
      <path class="root-stroke" d="M82 48 C 92 36, 88 20, 72 16 C 80 28, 82 38, 78 50"/>
      <path class="root-stroke" d="M30 82 C 18 78, 12 64, 16 54 C 22 68, 34 74, 42 76"/>
      <circle class="root-leaf" cx="27" cy="17" r="1.6"/>
      <circle class="root-leaf" cx="74" cy="15" r="1.4"/>
      <circle class="root-leaf" cx="15" cy="56" r="1.3"/>
    </svg>
  `;

  function enhanceAvatarHost(btn) {
    if (!btn || btn.closest(".profile-avatar-host")) return btn.closest(".profile-avatar-host");
    const host = document.createElement("div");
    host.className = "profile-avatar-host";
    if (btn.classList.contains("w-11") || btn.dataset.profileSize === "lg") {
      host.classList.add("is-lg");
    }
    btn.classList.add("profile-avatar-btn");
    // Eski boyut sınıflarını sadeleştir — CSS host yönetir
    ["w-10", "h-10", "w-11", "h-11", "rounded-full", "bg-primary-container",
      "text-on-primary-container", "border", "border-outline-variant",
      "flex", "items-center", "justify-center", "font-semibold", "shadow-sm",
      "hover:ring-2", "hover:ring-primary/30", "transition"].forEach((c) => btn.classList.remove(c));
    btn.parentNode.insertBefore(host, btn);
    host.insertAdjacentHTML("afterbegin", ROOT_SVG);
    host.appendChild(btn);
    return host;
  }

  function toast(msg) {
    let t = document.getElementById("profile-toast");
    if (!t) {
      t = document.createElement("div");
      t.id = "profile-toast";
      t.className =
        "fixed bottom-6 left-1/2 -translate-x-1/2 z-[80] px-4 py-2 rounded-lg bg-inverse-surface text-white text-sm shadow-lg opacity-0 transition-opacity pointer-events-none";
      document.body.appendChild(t);
    }
    t.textContent = msg;
    t.style.opacity = "1";
    clearTimeout(t._timer);
    t._timer = setTimeout(() => {
      t.style.opacity = "0";
    }, 2600);
  }

  async function refreshUser() {
    try {
      const me = await LI.me();
      Auth.setUser(me);
      paintAll();
      return me;
    } catch {
      paintAll();
      return Auth.user;
    }
  }

  function paintAll() {
    document.querySelectorAll("[data-profile-avatar]").forEach((el) => paintAvatar(el, Auth.user));
    document.querySelectorAll("[data-profile-name]").forEach((el) => {
      el.textContent = Auth.user?.name || Auth.user?.username || Auth.user?.email || "";
    });
  }

  function ensureUi() {
    if (document.getElementById("profile-menu-root")) return;

    const root = document.createElement("div");
    root.id = "profile-menu-root";
    root.innerHTML = `
      <input type="file" id="profile-avatar-file" accept="image/png,image/jpeg,image/webp,image/gif" class="hidden"/>
      <div id="profile-menu" class="hidden fixed z-[70] w-64 rounded-xl border border-outline-variant bg-surface-container-lowest shadow-xl py-2 text-sm text-on-surface">
        <div class="px-3 pb-2 mb-1 border-b border-outline-variant">
          <p class="text-[13px] font-semibold truncate" data-profile-name></p>
          <p class="text-[11px] text-on-surface-variant truncate" id="profile-menu-email"></p>
        </div>
        <div class="relative">
          <button type="button" id="profile-menu-photo" class="w-full flex items-center justify-between gap-2 px-3 py-2.5 hover:bg-surface-container text-left">
            <span class="flex items-center gap-2">
              <span class="material-symbols-outlined text-[18px] text-on-surface-variant">photo_camera</span>
              Profil fotoğrafını değiştir
            </span>
            <span class="material-symbols-outlined text-[18px] text-on-surface-variant">chevron_right</span>
          </button>
          <div id="profile-photo-submenu" class="hidden absolute right-0 top-full mt-1 w-52 rounded-xl border border-outline-variant bg-surface-container-lowest shadow-xl py-1 z-10">
            <button type="button" data-photo-action="add" class="w-full flex items-center gap-2 px-3 py-2.5 hover:bg-surface-container text-left">
              <span class="material-symbols-outlined text-[18px]">add_a_photo</span> Fotoğraf ekle
            </button>
            <button type="button" data-photo-action="icon" class="w-full flex items-center gap-2 px-3 py-2.5 hover:bg-surface-container text-left">
              <span class="material-symbols-outlined text-[18px]">emoji_emotions</span> İkon ekle
            </button>
            <button type="button" data-photo-action="remove" class="w-full flex items-center gap-2 px-3 py-2.5 hover:bg-surface-container text-left text-error">
              <span class="material-symbols-outlined text-[18px]">hide_image</span> Fotoğrafı kaldır
            </button>
          </div>
        </div>
        <a href="/hesap" class="flex items-center gap-2 px-3 py-2.5 hover:bg-surface-container">
          <span class="material-symbols-outlined text-[18px] text-on-surface-variant">manage_accounts</span>
          Hesap bilgileri
        </a>
        <button type="button" id="profile-menu-logout" class="w-full flex items-center gap-2 px-3 py-2.5 hover:bg-surface-container text-left border-t border-outline-variant mt-1">
          <span class="material-symbols-outlined text-[18px] text-on-surface-variant">logout</span>
          Çıkış yap
        </button>
      </div>
      <div id="profile-icon-modal" class="hidden fixed inset-0 z-[75] flex items-center justify-center p-4" style="background:rgba(34,26,22,0.45);backdrop-filter:blur(6px)">
        <div class="w-full max-w-md rounded-2xl bg-surface-container-lowest border border-outline-variant shadow-2xl p-5">
          <div class="flex items-center justify-between mb-4">
            <h3 class="text-lg font-semibold text-on-surface">İkon seç</h3>
            <button type="button" id="profile-icon-close" class="text-on-surface-variant hover:text-primary">
              <span class="material-symbols-outlined">close</span>
            </button>
          </div>
          <div id="profile-icon-grid" class="grid grid-cols-4 sm:grid-cols-5 gap-2"></div>
        </div>
      </div>
      <div id="profile-crop-modal" class="hidden fixed inset-0 z-[76] flex items-center justify-center p-4" style="background:rgba(34,26,22,0.5);backdrop-filter:blur(6px)">
        <div class="w-full max-w-lg rounded-2xl bg-surface-container-lowest border border-outline-variant shadow-2xl p-5">
          <div class="flex items-center justify-between mb-3">
            <div>
              <h3 class="text-lg font-semibold text-on-surface">Fotoğrafı kırp</h3>
              <p class="text-[12px] text-on-surface-variant mt-0.5">Sürükleyerek kaydır, kaydırıcıyla ölçekle</p>
            </div>
            <button type="button" id="profile-crop-close" class="text-on-surface-variant hover:text-primary">
              <span class="material-symbols-outlined">close</span>
            </button>
          </div>
          <div class="relative mx-auto w-full max-w-[320px] aspect-square rounded-2xl overflow-hidden bg-[#1a1410] border border-outline-variant touch-none select-none" id="profile-crop-stage">
            <canvas id="profile-crop-canvas" class="absolute inset-0 w-full h-full cursor-grab active:cursor-grabbing"></canvas>
            <div class="pointer-events-none absolute inset-0" style="background:radial-gradient(circle closest-side at center, transparent 69.8%, rgba(0,0,0,0.58) 70.2%);"></div>
            <div class="pointer-events-none absolute inset-[15%] rounded-full border-2 border-white/85"></div>
          </div>
          <div class="mt-4 flex items-center gap-3">
            <span class="material-symbols-outlined text-on-surface-variant text-[20px]">zoom_out</span>
            <input id="profile-crop-zoom" type="range" min="100" max="350" value="100" class="flex-1 accent-[#c2652a]"/>
            <span class="material-symbols-outlined text-on-surface-variant text-[20px]">zoom_in</span>
          </div>
          <div class="mt-4 flex justify-end gap-2">
            <button type="button" id="profile-crop-cancel" class="px-4 py-2 rounded-lg border border-outline-variant text-sm text-on-surface-variant hover:border-primary">Vazgeç</button>
            <button type="button" id="profile-crop-apply" class="px-5 py-2 rounded-lg text-sm font-semibold text-white" style="background:#c2652a">Kaydet</button>
          </div>
        </div>
      </div>
    `;
    document.body.appendChild(root);

    const menu = document.getElementById("profile-menu");
    const submenu = document.getElementById("profile-photo-submenu");
    const fileInput = document.getElementById("profile-avatar-file");
    const iconModal = document.getElementById("profile-icon-modal");
    const cropModal = document.getElementById("profile-crop-modal");
    const cropCanvas = document.getElementById("profile-crop-canvas");
    const cropZoom = document.getElementById("profile-crop-zoom");
    const cropCtx = cropCanvas.getContext("2d");
    const cropState = {
      img: null,
      objectUrl: null,
      scale: 1,
      minScale: 1,
      offsetX: 0,
      offsetY: 0,
      dragging: false,
      lastX: 0,
      lastY: 0,
    };

    function closeCropModal() {
      cropModal.classList.add("hidden");
      cropState.dragging = false;
      if (cropState.objectUrl) {
        URL.revokeObjectURL(cropState.objectUrl);
        cropState.objectUrl = null;
      }
      cropState.img = null;
    }

    function cropViewport() {
      const stage = document.getElementById("profile-crop-stage");
      const size = Math.min(stage.clientWidth || 320, stage.clientHeight || 320);
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      cropCanvas.width = Math.round(size * dpr);
      cropCanvas.height = Math.round(size * dpr);
      cropCanvas.style.width = size + "px";
      cropCanvas.style.height = size + "px";
      cropCtx.setTransform(dpr, 0, 0, dpr, 0, 0);
      return size;
    }

    function clampOffsets(viewSize) {
      if (!cropState.img) return;
      const dw = cropState.img.naturalWidth * cropState.scale;
      const dh = cropState.img.naturalHeight * cropState.scale;
      const maxX = Math.max(0, (dw - viewSize) / 2);
      const maxY = Math.max(0, (dh - viewSize) / 2);
      cropState.offsetX = Math.min(maxX, Math.max(-maxX, cropState.offsetX));
      cropState.offsetY = Math.min(maxY, Math.max(-maxY, cropState.offsetY));
    }

    function drawCrop() {
      if (!cropState.img) return;
      const size = cropViewport();
      clampOffsets(size);
      cropCtx.clearRect(0, 0, size, size);
      cropCtx.fillStyle = "#1a1410";
      cropCtx.fillRect(0, 0, size, size);
      const dw = cropState.img.naturalWidth * cropState.scale;
      const dh = cropState.img.naturalHeight * cropState.scale;
      const x = (size - dw) / 2 + cropState.offsetX;
      const y = (size - dh) / 2 + cropState.offsetY;
      cropCtx.imageSmoothingEnabled = true;
      cropCtx.imageSmoothingQuality = "high";
      cropCtx.drawImage(cropState.img, x, y, dw, dh);
    }

    function openCropModal(file) {
      if (cropState.objectUrl) URL.revokeObjectURL(cropState.objectUrl);
      const url = URL.createObjectURL(file);
      cropState.objectUrl = url;
      const img = new Image();
      img.onload = () => {
        cropState.img = img;
        const size = 320;
        const cover = Math.max(size / img.naturalWidth, size / img.naturalHeight);
        cropState.minScale = cover;
        cropState.scale = cover;
        cropState.offsetX = 0;
        cropState.offsetY = 0;
        cropZoom.min = "100";
        cropZoom.max = "350";
        cropZoom.value = "100";
        cropModal.classList.remove("hidden");
        requestAnimationFrame(drawCrop);
      };
      img.onerror = () => {
        URL.revokeObjectURL(url);
        toast("Görsel yüklenemedi");
      };
      img.src = url;
    }

    function exportCroppedBlob() {
      return new Promise((resolve, reject) => {
        if (!cropState.img) {
          reject(new Error("Görsel yok"));
          return;
        }
        // UI dairesi stage'in %70'i (inset %15) — ayni orani export et
        const out = 512;
        const viewSize = cropCanvas.clientWidth || 320;
        const cropRatio = 0.7;
        const cropPx = viewSize * cropRatio;
        const canvas = document.createElement("canvas");
        canvas.width = out;
        canvas.height = out;
        const ctx = canvas.getContext("2d");
        const scaleRatio = out / cropPx;
        const dw = cropState.img.naturalWidth * cropState.scale * scaleRatio;
        const dh = cropState.img.naturalHeight * cropState.scale * scaleRatio;
        // Gorunur dairenin merkezine gore hizala
        const x = (out - dw) / 2 + cropState.offsetX * scaleRatio;
        const y = (out - dh) / 2 + cropState.offsetY * scaleRatio;
        ctx.fillStyle = "#ffffff";
        ctx.fillRect(0, 0, out, out);
        ctx.save();
        ctx.beginPath();
        ctx.arc(out / 2, out / 2, out / 2, 0, Math.PI * 2);
        ctx.closePath();
        ctx.clip();
        ctx.imageSmoothingEnabled = true;
        ctx.imageSmoothingQuality = "high";
        ctx.drawImage(cropState.img, x, y, dw, dh);
        ctx.restore();
        canvas.toBlob(
          (blob) => {
            if (!blob) reject(new Error("Kırpma başarısız"));
            else resolve(blob);
          },
          "image/jpeg",
          0.92
        );
      });
    }

    cropZoom.addEventListener("input", () => {
      if (!cropState.img) return;
      const factor = Number(cropZoom.value) / 100;
      cropState.scale = cropState.minScale * factor;
      drawCrop();
    });

    cropCanvas.addEventListener("pointerdown", (e) => {
      cropState.dragging = true;
      cropState.lastX = e.clientX;
      cropState.lastY = e.clientY;
      cropCanvas.setPointerCapture(e.pointerId);
    });
    cropCanvas.addEventListener("pointermove", (e) => {
      if (!cropState.dragging) return;
      cropState.offsetX += e.clientX - cropState.lastX;
      cropState.offsetY += e.clientY - cropState.lastY;
      cropState.lastX = e.clientX;
      cropState.lastY = e.clientY;
      drawCrop();
    });
    const endDrag = () => {
      cropState.dragging = false;
    };
    cropCanvas.addEventListener("pointerup", endDrag);
    cropCanvas.addEventListener("pointercancel", endDrag);

    cropCanvas.addEventListener(
      "wheel",
      (e) => {
        if (!cropState.img || cropModal.classList.contains("hidden")) return;
        e.preventDefault();
        const next = Math.min(350, Math.max(100, Number(cropZoom.value) + (e.deltaY < 0 ? 8 : -8)));
        cropZoom.value = String(next);
        cropState.scale = cropState.minScale * (next / 100);
        drawCrop();
      },
      { passive: false }
    );

    document.getElementById("profile-crop-close").addEventListener("click", closeCropModal);
    document.getElementById("profile-crop-cancel").addEventListener("click", closeCropModal);
    cropModal.addEventListener("click", (e) => {
      if (e.target === cropModal) closeCropModal();
    });

    document.getElementById("profile-crop-apply").addEventListener("click", async () => {
      const btn = document.getElementById("profile-crop-apply");
      btn.disabled = true;
      btn.textContent = "Kaydediliyor…";
      try {
        const blob = await exportCroppedBlob();
        const file = new File([blob], "avatar.jpg", { type: "image/jpeg" });
        const user = await LI.uploadAvatar(file);
        Auth.setUser(user);
        paintAll();
        closeCropModal();
        toast("Profil fotoğrafı güncellendi");
      } catch (err) {
        toast(err.message || "Yükleme başarısız");
      } finally {
        btn.disabled = false;
        btn.textContent = "Kaydet";
      }
    });

    document.getElementById("profile-menu-photo").addEventListener("click", (e) => {
      e.stopPropagation();
      submenu.classList.toggle("hidden");
    });

    submenu.querySelectorAll("[data-photo-action]").forEach((btn) => {
      btn.addEventListener("click", async (e) => {
        e.stopPropagation();
        const action = btn.getAttribute("data-photo-action");
        submenu.classList.add("hidden");
        menu.classList.add("hidden");
        try {
          if (action === "add") {
            fileInput.click();
          } else if (action === "remove") {
            const user = await LI.clearAvatar();
            Auth.setUser(user);
            paintAll();
            toast("Profil fotoğrafı kaldırıldı");
          } else if (action === "icon") {
            openIconModal();
          }
        } catch (err) {
          toast(err.message || "İşlem başarısız");
        }
      });
    });

    fileInput.addEventListener("change", () => {
      const file = fileInput.files && fileInput.files[0];
      fileInput.value = "";
      if (!file) return;
      if (!file.type.startsWith("image/")) {
        toast("Lütfen bir görsel seç");
        return;
      }
      openCropModal(file);
    });

    document.getElementById("profile-menu-logout").addEventListener("click", () => {
      menu.classList.add("hidden");
      submenu.classList.add("hidden");
      if (window.ProfileMenu?.confirmLogout) ProfileMenu.confirmLogout();
      else {
        Auth.clear();
        window.location.href = "/";
      }
    });

    document.getElementById("profile-icon-close").addEventListener("click", () => {
      iconModal.classList.add("hidden");
    });
    iconModal.addEventListener("click", (e) => {
      if (e.target === iconModal) iconModal.classList.add("hidden");
    });

    document.addEventListener("click", (e) => {
      if (!menu.classList.contains("hidden") && !menu.contains(e.target) && !e.target.closest("[data-profile-trigger]")) {
        menu.classList.add("hidden");
        submenu.classList.add("hidden");
      }
    });

    async function openIconModal() {
      const grid = document.getElementById("profile-icon-grid");
      let icons = ICON_FALLBACK;
      try {
        const res = await LI.avatarIcons();
        if (res?.icons?.length) icons = res.icons;
      } catch {
        /* fallback */
      }
      grid.innerHTML = icons
        .map(
          (icon) => `
        <button type="button" data-icon="${icon}" class="aspect-square rounded-xl border border-outline-variant hover:border-primary hover:bg-primary-container flex items-center justify-center text-on-surface transition-colors" title="${icon}">
          <span class="material-symbols-outlined text-[26px]" style="font-variation-settings:'FILL' 1">${icon}</span>
        </button>`
        )
        .join("");
      grid.querySelectorAll("[data-icon]").forEach((btn) => {
        btn.addEventListener("click", async () => {
          try {
            const user = await LI.setAvatarIcon(btn.getAttribute("data-icon"));
            Auth.setUser(user);
            paintAll();
            iconModal.classList.add("hidden");
            toast("İkon güncellendi");
          } catch (err) {
            toast(err.message || "İkon seçilemedi");
          }
        });
      });
      iconModal.classList.remove("hidden");
    }
  }

  function positionMenu(anchor) {
    const menu = document.getElementById("profile-menu");
    const rect = anchor.getBoundingClientRect();
    const width = 256;
    let left = rect.right - width;
    if (left < 8) left = 8;
    let top = rect.bottom + 8;
    menu.style.left = `${left}px`;
    menu.style.top = `${top}px`;
    const emailEl = document.getElementById("profile-menu-email");
    if (emailEl) emailEl.textContent = Auth.user?.email || "";
    document.querySelectorAll("[data-profile-name]").forEach((el) => {
      el.textContent = Auth.user?.name || Auth.user?.username || Auth.user?.email || "";
    });
  }

  function bindTriggers() {
    document.querySelectorAll("[data-profile-trigger]").forEach((btn) => {
      enhanceAvatarHost(btn);
      if (btn._profileBound) return;
      btn._profileBound = true;
      btn.addEventListener("click", (e) => {
        e.stopPropagation();
        ensureUi();
        const menu = document.getElementById("profile-menu");
        const submenu = document.getElementById("profile-photo-submenu");
        const opening = menu.classList.contains("hidden");
        submenu.classList.add("hidden");
        if (opening) {
          positionMenu(btn);
          menu.classList.remove("hidden");
        } else {
          menu.classList.add("hidden");
        }
      });
    });
  }

  function ensureStylesheet() {
    if (document.getElementById("profile-avatar-css")) return;
    const link = document.createElement("link");
    link.id = "profile-avatar-css";
    link.rel = "stylesheet";
    link.href = "/static/css/profile-avatar.css";
    document.head.appendChild(link);
  }

  function enableDockDrag() {
    const dock = document.getElementById("app-profile-dock");
    if (!dock || dock._dragBound) return;
    dock._dragBound = true;

    const KEY = "betula_profile_dock_pos";
    const THRESHOLD = 10;
    let startX = 0;
    let startY = 0;
    let originLeft = 0;
    let originTop = 0;
    let tracking = false;
    let moved = false;
    let pointerId = null;

    function clamp(left, top) {
      const pad = 8;
      const w = dock.offsetWidth || 56;
      const h = dock.offsetHeight || 56;
      const maxL = Math.max(pad, window.innerWidth - w - pad);
      const maxT = Math.max(pad, window.innerHeight - h - pad);
      return {
        left: Math.min(maxL, Math.max(pad, left)),
        top: Math.min(maxT, Math.max(pad, top)),
      };
    }

    function applyPos(left, top) {
      const p = clamp(left, top);
      dock.classList.add("is-placed");
      dock.style.left = `${p.left}px`;
      dock.style.top = `${p.top}px`;
      dock.style.right = "auto";
      return p;
    }

    function restore() {
      try {
        const raw = localStorage.getItem(KEY);
        if (!raw) return;
        const pos = JSON.parse(raw);
        if (typeof pos?.left === "number" && typeof pos?.top === "number") {
          applyPos(pos.left, pos.top);
        }
      } catch {
        /* ignore */
      }
    }

    function save(left, top) {
      localStorage.setItem(KEY, JSON.stringify({ left, top }));
    }

    restore();

    const onMove = (e) => {
      if (!tracking) return;
      const dx = e.clientX - startX;
      const dy = e.clientY - startY;
      if (!moved && Math.hypot(dx, dy) < THRESHOLD) return;

      if (!moved) {
        moved = true;
        dock.classList.add("is-dragging");
        document.getElementById("profile-menu")?.classList.add("hidden");
        document.getElementById("profile-photo-submenu")?.classList.add("hidden");
        try {
          dock.setPointerCapture(pointerId);
        } catch {
          /* ignore */
        }
      }
      e.preventDefault();
      applyPos(originLeft + dx, originTop + dy);
    };

    const onUp = () => {
      if (!tracking) return;
      tracking = false;
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerup", onUp);
      window.removeEventListener("pointercancel", onUp);
      dock.classList.remove("is-dragging");

      if (pointerId != null) {
        try {
          dock.releasePointerCapture(pointerId);
        } catch {
          /* ignore */
        }
        pointerId = null;
      }

      if (moved) {
        const rect = dock.getBoundingClientRect();
        const p = applyPos(rect.left, rect.top);
        save(p.left, p.top);
        // Sürükleme bittikten sonra gelen click'i bir kerelik yut
        const swallow = (ev) => {
          ev.preventDefault();
          ev.stopPropagation();
          dock.removeEventListener("click", swallow, true);
        };
        dock.addEventListener("click", swallow, true);
      }
      // moved=false ise doğal click → profil menüsü açılır
      moved = false;
    };

    dock.addEventListener("pointerdown", (e) => {
      if (e.button != null && e.button !== 0) return;
      const rect = dock.getBoundingClientRect();
      startX = e.clientX;
      startY = e.clientY;
      originLeft = rect.left;
      originTop = rect.top;
      tracking = true;
      moved = false;
      pointerId = e.pointerId;
      // Capture HEMEN alma — eşik aşılmadan tıklama bozulmasın
      window.addEventListener("pointermove", onMove);
      window.addEventListener("pointerup", onUp);
      window.addEventListener("pointercancel", onUp);
    });

    window.addEventListener("resize", () => {
      if (!dock.classList.contains("is-placed")) return;
      const rect = dock.getBoundingClientRect();
      const p = applyPos(rect.left, rect.top);
      save(p.left, p.top);
    });
  }

  function mount() {
    if (!Auth.isLoggedIn()) return;
    ensureStylesheet();
    ensureUi();
    bindTriggers();
    enableDockDrag();
    paintAll();
    refreshUser();
  }

  function confirmLogout() {
    let modal = document.getElementById("logout-confirm-modal");
    if (!modal) {
      modal = document.createElement("div");
      modal.id = "logout-confirm-modal";
      modal.className = "fixed inset-0 z-[90] flex items-center justify-center p-4";
      modal.setAttribute("aria-hidden", "true");
      modal.innerHTML = `
        <div data-logout-backdrop class="absolute inset-0" style="background:rgba(34,26,22,0.48);backdrop-filter:blur(10px);-webkit-backdrop-filter:blur(10px)"></div>
        <div role="dialog" aria-modal="true" aria-labelledby="logout-confirm-title" class="relative z-10 w-full max-w-sm rounded-2xl border border-outline-variant bg-surface-container-lowest shadow-2xl p-5">
          <h3 id="logout-confirm-title" class="text-lg font-semibold text-on-surface">Çıkış</h3>
          <p class="mt-2 text-sm text-on-surface-variant leading-relaxed">Çıkmak istediğinizden emin misiniz?</p>
          <div class="mt-5 flex items-center justify-end gap-2">
            <button type="button" data-logout-cancel class="px-4 py-2 rounded-lg border border-outline-variant bg-white text-sm font-medium text-on-surface hover:bg-surface-container transition-colors">İptal</button>
            <button type="button" data-logout-confirm class="px-4 py-2 rounded-lg bg-error text-white text-sm font-semibold hover:opacity-90 transition-opacity">Evet, eminim</button>
          </div>
        </div>`;
      document.body.appendChild(modal);

      const close = () => {
        modal.classList.add("hidden");
        modal.setAttribute("aria-hidden", "true");
      };
      const doLogout = () => {
        Auth.clear();
        window.location.href = "/";
      };
      modal.querySelector("[data-logout-cancel]").addEventListener("click", close);
      modal.querySelector("[data-logout-backdrop]").addEventListener("click", close);
      modal.querySelector("[data-logout-confirm]").addEventListener("click", doLogout);
      document.addEventListener("keydown", (e) => {
        if (e.key === "Escape" && !modal.classList.contains("hidden")) close();
      });
    }
    modal.classList.remove("hidden");
    modal.setAttribute("aria-hidden", "false");
  }

  window.ProfileMenu = { mount, paintAll, refreshUser, paintAvatar, confirmLogout };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", mount);
  } else {
    mount();
  }
})();
