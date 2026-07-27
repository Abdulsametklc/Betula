/**
 * Wire Google / GitHub OAuth buttons in auth modals.
 */
(function () {
  function $(id) {
    return document.getElementById(id);
  }

  async function refreshOAuthButtons() {
    const wrap = $("oauth-buttons");
    if (!wrap || !window.LI) return;
    if (typeof window.authMode !== "undefined" && window.authMode === "forgot") {
      wrap.classList.add("hidden");
      $("oauth-divider")?.classList.add("hidden");
      return;
    }
    try {
      const data = await LI.oauthProviders();
      const providers = data.providers || {};
      const google = $("oauth-google");
      const github = $("oauth-github");
      if (google) {
        google.classList.toggle("hidden", !providers.google);
        google.disabled = !providers.google;
      }
      if (github) {
        github.classList.toggle("hidden", !providers.github);
        github.disabled = !providers.github;
      }
      const any = Boolean(providers.google || providers.github);
      wrap.classList.toggle("hidden", !any);
      const divider = $("oauth-divider");
      if (divider) divider.classList.toggle("hidden", !any);
    } catch {
      wrap.classList.add("hidden");
    }
  }
  window.refreshOAuthButtons = refreshOAuthButtons;

  function start(provider) {
    window.location.href = LI.oauthStartUrl(provider);
  }

  function wire() {
    $("oauth-google")?.addEventListener("click", () => start("google"));
    $("oauth-github")?.addEventListener("click", () => start("github"));
    refreshOAuthButtons();

    const params = new URLSearchParams(location.search);
    const err = params.get("oauth_error");
    if (err) {
      const el = $("auth-error");
      if (el) {
        el.textContent = err;
        el.classList.remove("hidden");
      }
      if (typeof window.openAuth === "function") openAuth("login");
      params.delete("oauth_error");
      const qs = params.toString();
      history.replaceState({}, "", `${location.pathname}${qs ? `?${qs}` : ""}${location.hash}`);
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", wire);
  } else {
    wire();
  }
})();
