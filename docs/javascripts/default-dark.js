// Force dark mode as default on first visit.
// MkDocs Material stores palette choice in localStorage under
// the key matching the site's data-md-color-switching attribute.
// If no preference is stored, set it to the dark (slate) palette index.
(function () {
  var key = __md_get("__palette");
  if (!key) {
    __md_set("__palette", { index: 0, color: { scheme: "slate", primary: "deep-purple", accent: "purple" } });
    document.body.setAttribute("data-md-color-scheme", "slate");
    document.body.setAttribute("data-md-color-primary", "deep-purple");
    document.body.setAttribute("data-md-color-accent", "purple");
  }
})();
