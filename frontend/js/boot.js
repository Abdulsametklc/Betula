/**
 * Betula boot — ikon fontu hazır olunca isim flaşını kapat.
 */
(function () {
  const html = document.documentElement;

  function markReady() {
    html.classList.add("betula-fonts-ready");
  }

  function waitFonts() {
    if (!document.fonts || !document.fonts.ready) return Promise.resolve();
    return document.fonts.ready;
  }

  function start() {
    Promise.race([
      waitFonts(),
      new Promise((r) => setTimeout(r, 900)),
    ]).then(markReady);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start, { once: true });
  } else {
    start();
  }
})();
