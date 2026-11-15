// Frappe Chat Translate for Raven: show each visible message in the viewer's language.
//
// Added to Raven's page (/raven) by frappe_chat_translate.raven_page. Raven is not modified: the
// script watches the message list, asks the server for translations of the messages on screen
// (cached per message and language on the server) and adds a line under each translated message.
// Runs only for users whose language is enabled in Chat Translate Settings.
(() => {
	"use strict";
	if (window.__fctRaven) return;
	window.__fctRaven = true;

	const API = "/api/method/frappe_chat_translate.translation.";
	const BOX = "fct-translation";
	const MAX_PER_REQUEST = 50;

	const translations = new Map(); // message id -> text ("" = nothing to show)
	const asked = new Map(); // message id -> text signature it was asked for
	const queue = new Set();
	let scanTimer = null;
	let flushing = false;

	const style = document.createElement("style");
	style.textContent = `
.${BOX}{margin:2px 0 4px 3.25rem;padding:2px 0 2px 8px;border-left:2px solid rgba(127,127,127,.45);
font-size:.875em;line-height:1.5;white-space:pre-wrap;word-break:break-word;opacity:.85}
.${BOX}[data-align="end"]{margin-left:auto;margin-right:.75rem;max-width:80%;text-align:right;
border-left:0;border-right:2px solid rgba(127,127,127,.45);padding:2px 8px 2px 0}
@media (max-width:767px){.${BOX}{margin-left:3rem}}`;
	document.head.appendChild(style);

	async function call(method, args) {
		const response = await fetch(API + method, {
			method: "POST",
			credentials: "same-origin",
			headers: {
				Accept: "application/json",
				"Content-Type": "application/json",
				"X-Frappe-CSRF-Token": window.csrf_token || "",
			},
			body: JSON.stringify(args || {}),
		});
		if (!response.ok) throw new Error(`${method}: HTTP ${response.status}`);
		return (await response.json()).message;
	}

	// The rows of the message list: Raven marks each with data-message-id, and the row itself (not an
	// image tile or the hover toolbar, which also carry the attribute) contains a data-message-row.
	function rows() {
		return [...document.querySelectorAll("[data-message-id]")].filter(
			(el) => el.querySelector("[data-message-row]") && !el.parentElement?.closest("[data-message-id]")
		);
	}

	function idsOf(row) {
		const members = row.getAttribute("data-batch-member");
		return members ? members.split(" ").filter(Boolean) : [row.getAttribute("data-message-id")];
	}

	function signature(row) {
		const body = row.querySelector("[data-message-row]");
		return (body ? body.textContent : "").trim();
	}

	function render(row) {
		const texts = idsOf(row)
			.map((id) => translations.get(id))
			.filter(Boolean);
		let box = row.querySelector(`:scope > .${BOX}`);
		if (!texts.length) {
			box?.remove();
			return;
		}
		if (!box) {
			box = document.createElement("div");
			box.className = BOX;
			box.setAttribute("lang", window.__fctLanguage || "");
			row.appendChild(box);
		}
		const align = row.querySelector("[data-message-row]")?.getAttribute("data-message-row");
		box.setAttribute("data-align", align === "end" ? "end" : "start");
		const text = texts.join("\n");
		if (box.textContent !== text) box.textContent = text; // text only, never HTML
	}

	function scan() {
		scanTimer = null;
		for (const row of rows()) {
			const sig = signature(row);
			for (const id of idsOf(row)) {
				if (!id) continue;
				if (asked.get(id) !== sig) {
					// new on screen, or edited since it was translated
					asked.set(id, sig);
					translations.delete(id);
					queue.add(id);
				}
			}
			render(row);
		}
		flush();
	}

	async function flush() {
		if (flushing || !queue.size) return;
		flushing = true;
		try {
			while (queue.size) {
				const batch = [...queue].slice(0, MAX_PER_REQUEST);
				batch.forEach((id) => queue.delete(id));
				let result = {};
				try {
					result = (await call("get_translations", { message_names: batch })) || {};
				} catch (e) {
					console.warn("Chat Translate:", e);
					batch.forEach((id) => asked.delete(id)); // try again on the next change
					break;
				}
				for (const id of batch) translations.set(id, result[id] || "");
			}
		} finally {
			flushing = false;
		}
		for (const row of rows()) render(row);
	}

	function schedule() {
		if (!scanTimer) scanTimer = setTimeout(scan, 300);
	}

	async function start() {
		let settings;
		try {
			settings = await call("get_client_settings");
		} catch (e) {
			console.warn("Chat Translate:", e);
			return;
		}
		if (!settings || !settings.enabled) return;
		window.__fctLanguage = settings.language;
		new MutationObserver((mutations) => {
			// ignore our own boxes being added or updated
			const ours = (m) => {
				const el = m.target.nodeType === 1 ? m.target : m.target.parentElement;
				if (el?.closest(`.${BOX}`)) return true;
				const changed = [...m.addedNodes, ...m.removedNodes];
				return changed.length > 0 && changed.every((n) => n.classList?.contains(BOX));
			};
			if (mutations.every(ours)) return;
			schedule();
		}).observe(document.body, { childList: true, subtree: true, characterData: true });
		schedule();
	}

	if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start);
	else start();
})();
