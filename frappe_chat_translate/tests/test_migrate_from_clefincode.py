"""Translations cached for ClefinCode Chat follow the messages to Raven."""

import json
import os
import tempfile

import frappe

try:
    from frappe.tests import IntegrationTestCase
except ImportError:  # Frappe v15
    from frappe.tests.utils import FrappeTestCase as IntegrationTestCase

from frappe_chat_translate import migrate_from_clefincode as mig
from frappe_chat_translate.tests.test_translation import JA_USER, VI_USER, WORKSPACE, ensure_user

DT = "Chat Message Translation"


class TestMigrateFromClefinCode(IntegrationTestCase):
    def setUp(self):
        frappe.set_user("Administrator")
        ensure_user(JA_USER, "Tr Ja", "ja")
        ensure_user(VI_USER, "Tr Vi", "vi")
        if not frappe.db.exists("Raven Workspace", WORKSPACE):
            frappe.get_doc(doctype="Raven Workspace", workspace_name=WORKSPACE, type="Private").insert(
                ignore_permissions=True
            )
        channel = frappe.get_doc(
            doctype="Raven Channel",
            channel_name=f"migration {frappe.generate_hash(length=6)}",
            type="Private",
            workspace=WORKSPACE,
        ).insert(ignore_permissions=True)
        self.channel = channel.name
        self.text = self.msg("<p>Hello</p>")
        self.caption = self.msg("<p>Look at this</p>")
        frappe.db.delete(DT)

    def msg(self, text):
        return (
            frappe.get_doc(doctype="Raven Message", channel_id=self.channel, message_type="Text", text=text)
            .insert(ignore_permissions=True)
            .name
        )

    def map_file(self, data):
        fd, path = tempfile.mkstemp(suffix=".json")
        with os.fdopen(fd, "w") as f:
            json.dump(data, f)
        self.addCleanup(os.remove, path)
        return path

    def stale_row(self, old, lang="ja"):
        doc = frappe.get_doc(doctype=DT, message=old, language=lang, source_language="en", text=f"{old}-{lang}")
        doc.db_insert()

    def test_rows_are_repointed_or_removed(self):
        self.stale_row("cc-text")
        self.stale_row("cc-image")
        self.stale_row("cc-deleted")
        path = self.map_file(
            {"messages": {"cc-text": self.text, "cc-image": "img"}, "captions": {"cc-image": self.caption}}
        )
        self.assertEqual(mig.run(path), {"repointed": 2, "removed": 1, "duplicates": 0, "added": 0})
        self.assertEqual(frappe.db.get_value(DT, {"text": "cc-text-ja"}, "message"), self.text)
        self.assertEqual(frappe.db.get_value(DT, {"text": "cc-image-ja"}, "message"), self.caption)
        self.assertEqual(frappe.db.get_value(DT, {"message": self.text}, "chat_channel"), self.channel)

    def test_saved_translations_are_added_to_an_empty_table(self):
        path = self.map_file(
            {
                "messages": {"cc-text": self.text},
                "captions": {},
                "translations": [
                    {"message": "cc-text", "language": "vi", "source_language": "en", "text": "Xin chào"},
                    {"message": "cc-gone", "language": "vi", "source_language": "en", "text": "x"},
                ],
            }
        )
        self.assertEqual(mig.run(path)["added"], 1)
        self.assertEqual(frappe.db.get_value(DT, {"message": self.text, "language": "vi"}, "text"), "Xin chào")

    def test_no_map_file_changes_nothing(self):
        self.stale_row("cc-text")
        self.assertIn("skipped", mig.run("/nonexistent.json"))
        self.assertTrue(frappe.db.exists(DT, {"message": "cc-text"}))

    def test_duplicates_keep_the_newest(self):
        frappe.db.sql_ddl(f"alter table `tab{DT}` drop index if exists unique_message_language")
        self.addCleanup(lambda: frappe.db.delete(DT))
        self.addCleanup(
            lambda: frappe.db.add_unique(DT, ["message", "language"], "unique_message_language")
        )
        for i, when in enumerate(("2026-11-01 10:00:00", "2026-11-02 10:00:00")):
            doc = frappe.get_doc(doctype=DT, message=self.text, language="ja", text=f"v{i}", creation=when)
            doc.db_insert()
        self.assertEqual(mig.remove_duplicates(), 1)
        self.assertEqual(frappe.db.get_value(DT, {"message": self.text}, "text"), "v1")
