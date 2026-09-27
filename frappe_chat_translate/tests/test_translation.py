"""Display-time translation with caching, without calling Claude: `call_claude` is replaced by a
stand-in that detects English/Japanese naively and prefixes the target language."""

from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from frappe_chat_translate import translation as t
from frappe_chat_translate.tests.test_guard import call, ensure_user, make_group

JA_USER = "tr.ja@example.com"
VI_USER = "tr.vi@example.com"
JA_USER_2 = "tr.ja2@example.com"
OUTSIDER = "tr.out@example.com"


def fake_claude(items, target, settings):
    out = {}
    for mid, text in items:
        source = "en" if text.isascii() else "ja"
        out[mid] = {"id": mid, "source_language": source, "text": text if source == target else f"[{target}] {text}"}
    return out


def get(user, *names):
    frappe.set_user(user)
    return call("frappe_chat_translate.translation.get_translations", message_names=frappe.as_json(list(names)))


class TestTranslation(IntegrationTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        for email, name, kind, lang in ((JA_USER, "Tr Ja", "System User", "ja"), (VI_USER, "Tr Vi", "Website User", "vi"),
                                        (JA_USER_2, "Tr Ja2", "Website User", "ja"), (OUTSIDER, "Tr Out", "Website User", "vi")):
            ensure_user(email, name, kind, roles=("Projects User",) if kind == "System User" else ())
            frappe.db.set_value("User", email, "language", lang)
        settings = frappe.get_doc("Chat Translate Settings")
        settings.enabled = 1
        settings.languages = ""
        settings.save(ignore_permissions=True)
        cls.room, _ = make_group("translation room", [JA_USER, VI_USER, JA_USER_2])
        frappe.db.commit()

    def tearDown(self):
        frappe.set_user("Administrator")

    def send(self, content):
        from clefincode_chat.api.api_1_3_4 import api as capi

        frappe.set_user("Administrator")
        return capi.send(content, "Administrator", self.room, "Administrator")["results"][0]["new_message_name"]

    def test_plain_text_strips_editor_html(self):
        self.assertEqual(t.plain_text("<p>こんにちは<br>BAL-001 &amp; <b>DOC</b></p>"), "こんにちは\nBAL-001 & DOC")

    @patch("frappe_chat_translate.translation.call_claude", side_effect=fake_claude)
    def test_everyone_reads_in_their_own_language(self, claude):
        english = self.send("<p>Please review the spec by Friday.</p>")
        self.assertEqual(get(JA_USER, english)[english], "[ja] Please review the spec by Friday.")
        self.assertEqual(get(VI_USER, english)[english], "[vi] Please review the spec by Friday.")

        japanese = self.send("<p>金曜日までに仕様を確認してください。</p>")
        self.assertEqual(get(VI_USER, japanese)[japanese], "[vi] 金曜日までに仕様を確認してください。")
        self.assertNotIn(japanese, get(JA_USER, japanese))  # already in Japanese: nothing to show

    @patch("frappe_chat_translate.translation.call_claude", side_effect=fake_claude)
    def test_cache_is_shared_per_language(self, claude):
        name = self.send("<p>The build is green.</p>")
        get(JA_USER, name)
        calls = claude.call_count
        self.assertEqual(get(JA_USER_2, name)[name], "[ja] The build is green.")  # same language: cache
        get(JA_USER, name)
        self.assertEqual(claude.call_count, calls)

    @patch("frappe_chat_translate.translation.call_claude", side_effect=fake_claude)
    def test_batch_translates_several_messages_in_one_call(self, claude):
        names = [self.send(f"<p>Message number {i}</p>") for i in range(3)]
        claude.reset_mock()
        result = get(VI_USER, *names)
        self.assertEqual(set(result), set(names))
        self.assertEqual(claude.call_count, 1)

    @patch("frappe_chat_translate.translation.call_claude", side_effect=fake_claude)
    def test_non_member_gets_nothing(self, claude):
        name = self.send("<p>Internal only.</p>")
        self.assertEqual(get(OUTSIDER, name), {})

    @patch("frappe_chat_translate.translation.call_claude", side_effect=fake_claude)
    def test_edit_clears_cache(self, claude):
        name = self.send("<p>Version one.</p>")
        get(VI_USER, name)
        frappe.set_user("Administrator")
        doc = frappe.get_doc("ClefinCode Chat Message", name)
        doc.content = "<p>Version two.</p>"
        doc.save(ignore_permissions=True)
        self.assertEqual(get(VI_USER, name)[name], "[vi] Version two.")

    def test_media_and_info_messages_are_skipped(self):
        doc = frappe._dict(is_deleted=0, is_media=1, is_document=0, is_voice_clip=0, is_screenshot=0,
                           message_type="", message_template_type="", content="x")
        self.assertFalse(t.is_translatable(doc))
        doc.update(is_media=0, message_type="info")
        self.assertFalse(t.is_translatable(doc))
        doc.update(message_type="")
        self.assertTrue(t.is_translatable(doc))

    def test_request_asks_for_source_language_per_message(self):
        req = t.build_request([("m1", "hi"), ("m2", "chào")], "ja", t.get_settings())
        item = req["output_config"]["format"]["schema"]["properties"]["items"]["items"]
        self.assertEqual(item["required"], ["id", "source_language", "text"])
        self.assertIn('<message id="m2">', req["messages"][0]["content"])


class TestEngines(IntegrationTestCase):
    def tearDown(self):
        settings = frappe.get_doc("Chat Translate Settings")
        settings.provider = "Anthropic Claude"
        settings.save(ignore_permissions=True)

    def test_gemini_config_requests_json_with_schema(self):
        system, user, schema = t.build_prompt([("m1", "hi")], "ja", t.get_settings())
        config = t.build_gemini_config(system, schema)
        self.assertEqual(config.response_mime_type, "application/json")
        self.assertEqual(config.response_json_schema, schema)
        self.assertEqual(config.system_instruction, system)

    def test_engine_follows_settings(self):
        settings = frappe.get_doc("Chat Translate Settings")
        settings.provider = "Google Gemini"
        settings.gemini_model = ""
        settings.save(ignore_permissions=True)
        self.assertEqual(t.model_name(t.get_settings()), "gemini-2.5-flash")
        with patch("frappe_chat_translate.translation.call_gemini", side_effect=fake_claude) as gemini, \
                patch("frappe_chat_translate.translation.call_claude") as claude:
            t.call_llm([("m1", "hello")], "ja", t.get_settings())
        gemini.assert_called_once()
        claude.assert_not_called()
