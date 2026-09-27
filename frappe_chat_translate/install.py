import os

import frappe
from frappe.modules.import_file import import_file_by_path


def ensure_chat_icon():
    """The apps-screen "Chat" icon is a standard Desktop Icon (desktop_icon/chat.json) that opens the
    Chat workspace. Versions up to 0.1.0 created an App-type icon of the same name from code; replace it."""
    # Frappe v15 has an older "Desktop Icon" DocType without icon_type; the v16 icon does not apply there
    if not frappe.db.has_column("Desktop Icon", "icon_type"):
        return
    if frappe.db.get_value("Desktop Icon", "Chat", "icon_type") == "App":
        frappe.delete_doc("Desktop Icon", "Chat", force=True, ignore_permissions=True)
        import_file_by_path(os.path.join(os.path.dirname(__file__), "desktop_icon", "chat.json"), force=True)
    frappe.clear_cache()


def can_manage_chat():
    """The Chat workspace (history and settings) is for System Manager and Chat Administrator."""
    return bool({"System Manager", "Chat Administrator"} & set(frappe.get_roles()))
