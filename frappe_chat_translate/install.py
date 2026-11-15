import frappe

# Up to 0.3.x the app shipped a "Chat" workspace, sidebar and apps-screen icon for ClefinCode Chat.
# From 0.4.0 Raven brings its own icon; the translation history and settings live in the
# "Chat Translate" workspace.
OLD_CHAT_RECORDS = (("Desktop Icon", "Chat"), ("Workspace Sidebar", "Chat"), ("Workspace", "Chat"))


def after_install():
    remove_old_chat_records()
    ensure_unique_translations()
    frappe.clear_cache()


def ensure_unique_translations():
    """The unique (message, language) index, also on sites whose DocType was already up to date
    (on_doctype_update runs only when the DocType changes)."""
    from frappe_chat_translate.chat_translate.doctype.chat_message_translation.chat_message_translation import (
        on_doctype_update,
    )
    from frappe_chat_translate.migrate_from_clefincode import remove_duplicates

    remove_duplicates()
    on_doctype_update()


def remove_old_chat_records():
    for doctype, name in OLD_CHAT_RECORDS:
        if not frappe.db.table_exists(doctype) or not frappe.db.exists(doctype, name):
            continue
        if frappe.db.has_column(doctype, "app") and frappe.db.get_value(doctype, name, "app") not in (
            None,
            "",
            "frappe_chat_translate",
        ):
            continue  # someone else's record with the same name
        frappe.delete_doc(doctype, name, force=True, ignore_permissions=True)
