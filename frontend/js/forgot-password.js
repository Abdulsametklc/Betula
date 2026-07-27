/**
 * Forgot / reset password UI shared by index + about auth modals.
 * Expects elements: #auth-modal, #forgot-*, #auth-* and LI + Auth globals.
 */
(function () {
  const $ = (id) => document.getElementById(id);

  function show(el, on) {
    if (!el) return;
    el.classList.toggle("hidden", !on);
  }

  function setErr(msg) {
    const err = $("auth-error");
    if (!err) return;
    if (!msg) {
      err.classList.add("hidden");
      err.textContent = "";
      return;
    }
    err.textContent = msg;
    err.classList.remove("hidden");
  }

  function setHint(msg) {
    const hint = $("forgot-hint");
    if (!hint) return;
    if (!msg) {
      hint.classList.add("hidden");
      hint.textContent = "";
      return;
    }
    hint.textContent = msg;
    hint.classList.remove("hidden");
  }

  window.ForgotPassword = {
    step: "request", // request | code | new
    identifier: "",
    code: "",

    open() {
      this.step = "request";
      this.identifier = "";
      this.code = "";
      if ($("forgot-identifier")) $("forgot-identifier").value = "";
      if ($("forgot-code")) $("forgot-code").value = "";
      if ($("forgot-password")) $("forgot-password").value = "";
      if ($("forgot-password2")) $("forgot-password2").value = "";
      setErr("");
      setHint("");
      this.sync();
      if (typeof window.openAuth === "function") {
        window.openAuth("forgot");
      }
    },

    sync() {
      const isForgot = typeof window.authMode !== "undefined" && window.authMode === "forgot";
      show($("auth-login-fields"), !isForgot);
      show($("forgot-panel"), isForgot);
      show($("auth-toggle"), !isForgot);
      show($("forgot-back"), isForgot);

      if (!isForgot) return;

      if ($("auth-title")) $("auth-title").textContent = "Şifremi unuttum";
      const sub = $("auth-subtitle");
      if (sub) {
        sub.textContent =
          this.step === "request"
            ? "E-posta veya kullanıcı adınla sıfırlama kodu iste."
            : this.step === "code"
              ? "E-postandaki 6 haneli aktivasyon kodunu gir."
              : "Yeni şifreni belirle.";
      }

      show($("forgot-step-request"), this.step === "request");
      show($("forgot-step-code"), this.step === "code");
      show($("forgot-step-new"), this.step === "new");
    },

    async sendCode() {
      setErr("");
      const identifier = ($("forgot-identifier")?.value || "").trim();
      if (!identifier) {
        setErr("E-posta veya kullanıcı adı gir");
        return;
      }
      try {
        const res = await LI.forgotPassword(identifier);
        this.identifier = identifier;
        let hint = res.email_hint
          ? `Kod ${res.email_hint} adresine gönderildi.`
          : res.message || "Eslesen hesap varsa kod e-postaya gonderildi.";
        if (res.dev_code) hint += ` (Geliştirme kodu: ${res.dev_code})`;
        setHint(hint);
        this.step = "code";
        this.sync();
        $("forgot-code")?.focus();
      } catch (e) {
        setErr(e.message || "Kod gönderilemedi");
      }
    },

    async verifyCode() {
      setErr("");
      const code = ($("forgot-code")?.value || "").trim();
      if (code.length < 4) {
        setErr("Aktivasyon kodunu gir");
        return;
      }
      try {
        await LI.verifyResetCode(this.identifier, code);
        this.code = code;
        this.step = "new";
        this.sync();
        $("forgot-password")?.focus();
      } catch (e) {
        setErr(e.message || "Kod dogrulanamadi");
      }
    },

    async submitNewPassword() {
      setErr("");
      const a = $("forgot-password")?.value || "";
      const b = $("forgot-password2")?.value || "";
      if (a.length < 6) {
        setErr("Sifre en az 6 karakter olmali");
        return;
      }
      if (a !== b) {
        setErr("Yeni sifreler eslesmiyor");
        return;
      }
      try {
        await LI.resetPassword(this.identifier, this.code, a);
        setHint("Sifren guncellendi. Simdi giris yapabilirsin.");
        this.step = "request";
        if (typeof window.openAuth === "function") window.openAuth("login");
        setErr("");
        const emailField = $("auth-email");
        if (emailField && this.identifier.includes("@")) {
          emailField.value = this.identifier;
        }
      } catch (e) {
        setErr(e.message || "Sifre guncellenemedi");
      }
    },
  };

  function wire() {
    $("auth-forgot-link")?.addEventListener("click", (e) => {
      e.preventDefault();
      ForgotPassword.open();
    });
    $("forgot-back")?.addEventListener("click", () => {
      if (typeof window.openAuth === "function") window.openAuth("login");
    });
    $("forgot-send")?.addEventListener("click", () => ForgotPassword.sendCode());
    $("forgot-resend")?.addEventListener("click", () => ForgotPassword.sendCode());
    $("forgot-verify")?.addEventListener("click", () => ForgotPassword.verifyCode());
    $("forgot-confirm")?.addEventListener("click", () => ForgotPassword.submitNewPassword());
    $("forgot-code")?.addEventListener("keydown", (e) => {
      if (e.key === "Enter") ForgotPassword.verifyCode();
    });

    const params = new URLSearchParams(location.search);
    if (params.get("reset") === "1") {
      // openAuth may be defined by the page script after this file; defer one tick.
      setTimeout(() => ForgotPassword.open(), 0);
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", wire);
  } else {
    wire();
  }
})();
