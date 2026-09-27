// Shows each ClefinCode Chat message in the viewer's language, under the original bubble.
// Visible messages (history and newly arrived ones) are translated on display, in batches;
// the server caches per (message, language) and this page caches per message.
(function () {
  if (window.__chat_translate_loaded) return;
  window.__chat_translate_loaded = true;

  const METHOD = "frappe_chat_translate.translation.";
  const cache = new Map(); // message name -> translation text ("" = none)
  let pending = new Set();
  let timer = null;

  function currentUser() {
    // desk: frappe.session.user after boot; portal pages: the user_id cookie
    if (!window.frappe) return null;
    const user = (frappe.session && frappe.session.user) || (frappe.get_cookie && frappe.get_cookie("user_id"));
    return user && user !== "Guest" ? decodeURIComponent(user) : null;
  }

  // this file runs before the desk has booted: wait until frappe and the session are ready
  function whenReady(callback, tries = 0) {
    if (window.frappe && frappe.call && currentUser()) return callback();
    if (tries < 50) setTimeout(() => whenReady(callback, tries + 1), 200);
  }

  function render(name, text) {
    if (!text) return;
    document.querySelectorAll(`[data-message-name="${CSS.escape(name)}"] .message-bubble`).forEach((bubble) => {
      if (bubble.querySelector(".ct-translation")) return;
      const box = document.createElement("div");
      box.className = "ct-translation";
      box.style.cssText =
        "margin-top:6px;padding-top:6px;border-top:1px dashed rgba(0,0,0,.2);font-size:.92em;opacity:.85;white-space:pre-wrap;";
      box.textContent = text;
      box.title = __("Machine translation (click to hide)");
      box.addEventListener("click", () => (box.style.display = "none"));
      bubble.appendChild(box);
    });
  }

  function flush() {
    timer = null;
    const names = [...pending].filter((n) => !cache.has(n));
    pending = new Set();
    if (!names.length) return;
    frappe.call({
      method: METHOD + "get_translations",
      args: { message_names: JSON.stringify(names) },
      callback: (r) => {
        const found = (r && r.message) || {};
        names.forEach((n) => {
          cache.set(n, found[n] || "");
          render(n, found[n]);
        });
      },
    });
  }

  function queue(name) {
    if (!name) return;
    if (cache.has(name)) return render(name, cache.get(name));
    pending.add(name);
    if (!timer) timer = setTimeout(flush, 400);
  }

  function scan(root) {
    if (!root.querySelectorAll) return;
    if (root.matches && root.matches("[data-message-name]")) queue(root.getAttribute("data-message-name"));
    root.querySelectorAll("[data-message-name]").forEach((el) => queue(el.getAttribute("data-message-name")));
  }

  // Appearance of ClefinCode's floating chat button, from Chat Translate Settings. ClefinCode
  // re-renders the button when the panel opens and closes, so the icon is re-applied on changes.
  function style_chat_button(button) {
    if (!button) return;
    const size = button.size || 56;
    const side = button.position === "left" ? "left: 24px !important; right: auto !important;" : "";
    const css = `
      body #chat-bubble { bottom: 24px !important; ${side} }
      body #chat-bubble .chat-bubble:not(.chat-bubble-closed) {
        width: ${size}px; height: ${size}px; padding: 0 !important; border-radius: 50%;
        display: flex; align-items: center; justify-content: center; overflow: hidden;
        ${button.color ? `background: ${button.color} !important;` : ""}
        box-shadow: 0 2px 8px rgba(0, 0, 0, .2);
      }
      body #chat-bubble .chat-bubble:not(.chat-bubble-closed) img {
        width: ${Math.round(size * (button.color ? 0.6 : 1))}px; height: auto; max-height: 100%;
      }`;
    let style = document.getElementById("ct-chat-button-style");
    if (!style) {
      style = document.createElement("style");
      style.id = "ct-chat-button-style";
      document.head.appendChild(style);
    }
    style.textContent = css;
    if (!button.icon) return;
    const apply_icon = () => {
      document.querySelectorAll("#chat-bubble .chat-bubble:not(.chat-bubble-closed) img").forEach((img) => {
        if (img.getAttribute("src") !== button.icon) img.setAttribute("src", button.icon);
      });
    };
    apply_icon();
    new MutationObserver(apply_icon).observe(document.body, { childList: true, subtree: true });
  }

  function start(settings) {
    if (!settings) return;
    style_chat_button(settings.button);
    if (!settings.enabled) return;
    // new messages arrive through ClefinCode's own realtime and are added to the DOM:
    // translate whatever becomes visible
    new MutationObserver((mutations) => {
      mutations.forEach((m) => m.addedNodes.forEach((node) => node.nodeType === 1 && scan(node)));
    }).observe(document.body, { childList: true, subtree: true });
    scan(document.body);
  }

  // Open ClefinCode's chat panel on the current page. ClefinCode binds the bubble's click handler
  // some time after the bubble appears, so a click right away is lost: click, check that the
  // panel (.chat-container) opened, retry if not.
  function open_chat_panel() {
    const shown = (el) =>
      !!el && el.getClientRects().length > 0 && getComputedStyle(el).visibility !== "hidden";
    let tries = 0;
    const timer = setInterval(() => {
      if (shown(document.querySelector(".chat-container")) || ++tries > 20) return clearInterval(timer);
      const bubble = document.getElementById("chat-bubble");
      if (shown(bubble)) bubble.click();
    }, 700);
  }

  const is_chat_url = (url) => {
    try {
      const u = new URL(url, window.location.href);
      return u.origin === window.location.origin && u.searchParams.get("chat") === "1";
    } catch (e) {
      return false;
    }
  };

  // "Open Chat" (workspace shortcut and sidebar) points at /desk?chat=1: open the panel in place
  // instead of navigating or opening a new tab.
  function intercept_chat_links() {
    document.addEventListener(
      "click",
      (event) => {
        const link = event.target.closest && event.target.closest("a[href]");
        if (link && is_chat_url(link.getAttribute("href"))) {
          event.preventDefault();
          event.stopPropagation();
          open_chat_panel();
        }
      },
      true
    );
    const original_open = window.open;
    window.open = function (url, ...rest) {
      if (typeof url === "string" && is_chat_url(url)) {
        open_chat_panel();
        return null;
      }
      return original_open.call(window, url, ...rest);
    };
  }

  // a direct visit to /desk?chat=1 (bookmark, old icon) also opens the panel
  function open_chat_from_url() {
    const params = new URLSearchParams(window.location.search);
    if (params.get("chat") !== "1") return;
    params.delete("chat");
    const rest = params.toString();
    history.replaceState(null, "", window.location.pathname + (rest ? "?" + rest : "") + window.location.hash);
    open_chat_panel();
  }

  function init() {
    intercept_chat_links();
    open_chat_from_url();
    frappe.call({ method: METHOD + "get_client_settings", callback: (r) => start(r && r.message) });
  }

  const run = () => whenReady(init);
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", run);
  else run();
})();
