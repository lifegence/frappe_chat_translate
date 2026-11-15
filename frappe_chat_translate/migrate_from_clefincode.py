"""Carry translations made for ClefinCode Chat over to the Raven messages they were converted to.

The conversion of ClefinCode Chat to Raven (done outside this app) writes a map file
`private/files/clefincode_raven_map.json`:
    {"messages": {old id: Raven Message}, "captions": {old id: Raven Message}, "translations": [...]}
"captions" are the text messages split off image messages; a translation belongs to the text, so it
goes to the caption when there is one.

- Rows still pointing at ClefinCode messages are re-pointed (or removed when the message was not
  converted, e.g. a deleted message).
- When the table is empty (the old app was uninstalled), the translations saved in the map are added.
Without the map file nothing is changed: the chat may not be converted yet (the bench can already run
0.4.0 while ClefinCode Chat is still installed), and the conversion calls this again when it is done.
Runs from the v0.4 patch and from the conversion; can also be run again by hand:
    bench --site SITE execute frappe_chat_translate.migrate_from_clefincode.run
"""

import json
import os

import frappe

MAP_FILE = "clefincode_raven_map.json"
DT = "Chat Message Translation"


def load_map(path: str | None = None) -> dict | None:
    path = path or frappe.get_site_path("private", "files", MAP_FILE)
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def target(m: dict, old: str) -> str | None:
    return (m.get("captions") or {}).get(old) or (m.get("messages") or {}).get(old)


def run(path: str | None = None) -> dict:
    if not frappe.db.table_exists("Raven Message"):
        return {"skipped": "Raven is not installed"}
    m = load_map(path)
    if m is None:
        return {"skipped": "no map file (chat not converted yet)"}
    stats = {"repointed": 0, "removed": 0, "added": 0}
    channel_of = {}

    def channel(raven_msg):
        if raven_msg not in channel_of:
            channel_of[raven_msg] = frappe.db.get_value("Raven Message", raven_msg, "channel_id")
        return channel_of[raven_msg]

    # rows whose message is not a Raven message: made for ClefinCode Chat
    rm = frappe.qb.DocType("Raven Message")
    t = frappe.qb.DocType(DT)
    stale = (
        frappe.qb.from_(t)
        .left_join(rm)
        .on(rm.name == t.message)
        .select(t.name, t.message)
        .where(rm.name.isnull())
        .run(as_dict=True)
    )
    for row in stale:
        new = target(m, row.message)
        if new and frappe.db.exists("Raven Message", new):
            frappe.db.set_value(DT, row.name, {"message": new, "chat_channel": channel(new)}, update_modified=False)
            stats["repointed"] += 1
        else:
            frappe.db.delete(DT, {"name": row.name})
            stats["removed"] += 1

    if not frappe.db.count(DT):
        for tr in m.get("translations") or []:
            new = target(m, tr.get("message"))
            if not new or not frappe.db.exists("Raven Message", new):
                continue
            if frappe.db.exists(DT, {"message": new, "language": tr.get("language")}):
                continue
            doc = frappe.get_doc(
                doctype=DT,
                message=new,
                chat_channel=channel(new),
                language=tr.get("language"),
                source_language=tr.get("source_language"),
                text=tr.get("text"),
                model=tr.get("model"),
            )
            doc.db_insert()
            stats["added"] += 1
    frappe.db.commit()
    return stats
