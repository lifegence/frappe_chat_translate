"""Add the translation script to Raven's web app page (/raven and its client-side routes).

Raven renders /raven from its own template, which has no hook for other apps' scripts, so the
script tag is added to the finished HTML response. Only successful HTML responses for Raven's
page are touched; API calls, assets and every other page pass through unchanged.
"""

import frappe

from frappe_chat_translate import __version__

SCRIPT = (
    '<script src="/assets/frappe_chat_translate/js/raven_translate.js?v={v}" defer></script>'
)


def is_raven_page(path: str) -> bool:
    return path == "/raven" or path.startswith("/raven/")


def add_translation_script(response=None, request=None):
    if response is None or request is None or not is_raven_page(request.path or ""):
        return
    if response.status_code != 200 or response.mimetype != "text/html" or response.direct_passthrough:
        return
    if frappe.session.user == "Guest":
        return
    html = response.get_data(as_text=True)
    if "raven_translate.js" in html or "</body>" not in html:
        return
    tag = SCRIPT.format(v=__version__)
    head, _, tail = html.rpartition("</body>")
    response.set_data(f"{head}{tag}\n</body>{tail}")
