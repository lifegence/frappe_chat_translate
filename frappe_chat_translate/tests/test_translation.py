"""Display-time translation with caching, without calling a translation engine: `call_llm` (any
engine) is replaced by a stand-in that detects English/Japanese naively and prefixes the target
language. The OpenAI engine is tested against a mocked client."""

from unittest.mock import patch

import frappe

try:
    from frappe.tests import IntegrationTestCase
except ImportError:  # Frappe v15
    from frappe.tests.utils import FrappeTestCase as IntegrationTestCase

from frappe_chat_translate import translation as t

JA_USER = "tr.ja@example.com"
VI_USER = "tr.vi@example.com"
JA_USER_2 = "tr.ja2@example.com"
OUTSIDER = "tr.out@example.com"
WORKSPACE = "Chat Translate Test"


def fake_engine(items, target, settings):
    out = {}
    for mid, text in items:
        source = "en" if text.isascii() else "ja"
        out[mid] = {
            "id": mid,
            "source_language": source,
            "text": text if source == target else f"[{target}] {text}",
        }
    return out


def ensure_user(email, first_name, lang):
    if not frappe.db.exists("User", email):
        frappe.get_doc(
            doctype="User",
            email=email,
            first_name=first_name,
            user_type="System User",
            send_welcome_email=0,
            roles=[{"role": "Raven User"}],
        ).insert(ignore_permissions=True)
    frappe.db.set_value("User", email, "language", lang)


def get(user, *names):
    frappe.set_user(user)
    try:
        return t.get_translations(frappe.as_json(list(names)))
    finally:
        frappe.set_user("Administrator")


class TestTranslation(IntegrationTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        for email, name, lang in (
            (JA_USER, "Tr Ja", "ja"),
            (VI_USER, "Tr Vi", "vi"),
            (JA_USER_2, "Tr Ja2", "ja"),
            (OUTSIDER, "Tr Out", "vi"),
        ):
            ensure_user(email, name, lang)
        settings = frappe.get_doc("Chat Translate Settings")
        settings.enabled = 1
        settings.languages = ""
        settings.save(ignore_permissions=True)
        if not frappe.db.exists("Raven Workspace", WORKSPACE):
            frappe.get_doc(doctype="Raven Workspace", workspace_name=WORKSPACE, type="Private").insert(
                ignore_permissions=True
            )
        channel = frappe.get_doc(
            doctype="Raven Channel",
            channel_name=f"translation room {frappe.generate_hash(length=6)}",
            type="Private",
            workspace=WORKSPACE,
        ).insert(ignore_permissions=True)
        channel.add_members([JA_USER, VI_USER, JA_USER_2])
        cls.channel = channel.name
        frappe.db.commit()

    def tearDown(self):
        frappe.set_user("Administrator")

    def send(self, text, **values):
        return (
            frappe.get_doc(
                doctype="Raven Message",
                channel_id=self.channel,
                message_type="Text",
                text=text,
                **values,
            )
            .insert(ignore_permissions=True)
            .name
        )

    def test_plain_text_strips_editor_html(self):
        self.assertEqual(
            t.plain_text("<p>こんにちは<br>BAL-001 &amp; <b>DOC</b></p>"), "こんにちは\nBAL-001 & DOC"
        )

    @patch("frappe_chat_translate.translation.call_llm", side_effect=fake_engine)
    def test_everyone_reads_in_their_own_language(self, engine):
        english = self.send("<p>Please review the spec by Friday.</p>")
        self.assertEqual(get(JA_USER, english)[english], "[ja] Please review the spec by Friday.")
        self.assertEqual(get(VI_USER, english)[english], "[vi] Please review the spec by Friday.")

        japanese = self.send("<p>金曜日までに仕様を確認してください。</p>")
        self.assertEqual(get(VI_USER, japanese)[japanese], "[vi] 金曜日までに仕様を確認してください。")
        self.assertNotIn(japanese, get(JA_USER, japanese))  # already in Japanese: nothing to show

    @patch("frappe_chat_translate.translation.call_llm", side_effect=fake_engine)
    def test_cache_is_shared_per_language(self, engine):
        name = self.send("<p>The build is green.</p>")
        get(JA_USER, name)
        calls = engine.call_count
        self.assertEqual(get(JA_USER_2, name)[name], "[ja] The build is green.")  # same language: cache
        get(JA_USER, name)
        self.assertEqual(engine.call_count, calls)

    @patch("frappe_chat_translate.translation.call_llm", side_effect=fake_engine)
    def test_batch_translates_several_messages_in_one_call(self, engine):
        names = [self.send(f"<p>Message number {i}</p>") for i in range(3)]
        engine.reset_mock()
        result = get(VI_USER, *names)
        self.assertEqual(set(result), set(names))
        self.assertEqual(engine.call_count, 1)

    @patch("frappe_chat_translate.translation.call_llm", side_effect=fake_engine)
    def test_non_member_gets_nothing(self, engine):
        name = self.send("<p>Internal only.</p>")
        self.assertEqual(get(OUTSIDER, name), {})
        engine.assert_not_called()

    @patch("frappe_chat_translate.translation.call_llm", side_effect=fake_engine)
    def test_edit_clears_cache(self, engine):
        name = self.send("<p>Version one.</p>")
        get(VI_USER, name)
        doc = frappe.get_doc("Raven Message", name)
        doc.text = "<p>Version two.</p>"
        doc.save(ignore_permissions=True)
        self.assertEqual(get(VI_USER, name)[name], "[vi] Version two.")

    @patch("frappe_chat_translate.translation.call_llm", side_effect=fake_engine)
    def test_delete_removes_cached_translations(self, engine):
        name = self.send("<p>Short lived.</p>")
        get(VI_USER, name)
        self.assertTrue(frappe.db.exists("Chat Message Translation", {"message": name}))
        frappe.delete_doc("Raven Message", name, ignore_permissions=True, force=True)
        self.assertFalse(frappe.db.exists("Chat Message Translation", {"message": name}))

    @patch("frappe_chat_translate.translation.call_llm", side_effect=fake_engine)
    def test_translation_equal_to_original_is_not_shown(self, engine):
        name = self.send("<p>https://example.com/x</p>")
        t._store(name, self.channel, "vi", "en", "https://example.com/x", "m")
        self.assertEqual(get(VI_USER, name), {})

    def test_store_twice_keeps_one(self):
        name = self.send("<p>Once.</p>")
        t._store(name, self.channel, "vi", "en", "[vi] Once.", "m")
        with patch.object(frappe.db, "exists", return_value=False):  # the race: both checked first
            t._store(name, self.channel, "vi", "en", "[vi] Once.", "m")
        self.assertEqual(frappe.db.count("Chat Message Translation", {"message": name, "language": "vi"}), 1)

    def test_files_polls_and_bots_are_skipped(self):
        doc = frappe._dict(message_type="File", is_bot_message=0, text="x")
        self.assertFalse(t.is_translatable(doc))
        doc.update(message_type="Text", is_bot_message=1)
        self.assertFalse(t.is_translatable(doc))
        doc.update(is_bot_message=0)
        self.assertTrue(t.is_translatable(doc))
        doc.update(text="<p> </p>")
        self.assertFalse(t.is_translatable(doc))

    def test_client_settings(self):
        frappe.set_user(VI_USER)
        self.assertEqual(t.get_client_settings(), {"enabled": True, "language": "vi"})

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
        with (
            patch("frappe_chat_translate.translation.call_gemini", side_effect=fake_engine) as gemini,
            patch("frappe_chat_translate.translation.call_claude") as claude,
        ):
            t.call_llm([("m1", "hello")], "ja", t.get_settings())
        gemini.assert_called_once()
        claude.assert_not_called()


class OpenAISettings(frappe._dict):
    """Settings stand-in for the OpenAI engine (no database)."""

    def get_password(self, fieldname, raise_exception=True):
        return self.get(fieldname)


def openai_settings(**values):
    defaults = dict(
        provider="OpenAI",
        openai_api_key="test-key",
        openai_model="",
        openai_base_url="",
        effort="low",
        glossary="",
        translation_context="",
    )
    return OpenAISettings({**defaults, **values})


def openai_response(content, finish_reason="stop", refusal=None):
    message = frappe._dict(content=content, refusal=refusal)
    return frappe._dict(choices=[frappe._dict(message=message, finish_reason=finish_reason)])


def bad_request():
    import httpx
    import openai

    response = httpx.Response(400, request=httpx.Request("POST", "http://test/v1/chat/completions"))
    return openai.BadRequestError("response_format is not supported", response=response, body=None)


TRANSLATED = '{"items": [{"id": "m1", "source_language": "en", "text": "[ja] hello"}]}'


class TestOpenAI(IntegrationTestCase):
    def test_default_model(self):
        self.assertEqual(t.model_name(openai_settings()), "gpt-6-sol")
        self.assertEqual(t.model_name(openai_settings(openai_model="my-deployment")), "my-deployment")

    def test_request_uses_structured_output_and_effort(self):
        req = t.build_openai_request([("m1", "hi")], "ja", openai_settings())
        self.assertEqual(req["response_format"]["type"], "json_schema")
        self.assertTrue(req["response_format"]["json_schema"]["strict"])
        self.assertEqual(req["reasoning_effort"], "low")
        self.assertEqual(req["max_completion_tokens"], 16000)
        self.assertEqual([m["role"] for m in req["messages"]], ["system", "user"])

    def test_base_url_request_leaves_out_effort(self):
        req = t.build_openai_request([("m1", "hi")], "ja", openai_settings(openai_base_url="http://llm/v1"))
        self.assertNotIn("reasoning_effort", req)
        self.assertEqual(req["response_format"]["type"], "json_schema")

    def test_json_mode_request_carries_schema_in_instructions(self):
        req = t.build_openai_request([("m1", "hi")], "ja", openai_settings(), strict=False)
        self.assertEqual(req["response_format"], {"type": "json_object"})
        self.assertEqual(req["max_tokens"], 16000)
        self.assertNotIn("max_completion_tokens", req)
        self.assertIn('"source_language"', req["messages"][0]["content"])

    def test_engine_follows_settings(self):
        with (
            patch("frappe_chat_translate.translation.call_openai", side_effect=fake_engine) as engine,
            patch("frappe_chat_translate.translation.call_claude") as claude,
        ):
            t.call_llm([("m1", "hello")], "ja", openai_settings())
        engine.assert_called_once()
        claude.assert_not_called()

    @patch("openai.OpenAI")
    def test_translates(self, client_class):
        create = client_class.return_value.chat.completions.create
        create.return_value = openai_response(TRANSLATED)
        rows = t.call_openai([("m1", "hello")], "ja", openai_settings())
        self.assertEqual(rows["m1"]["text"], "[ja] hello")
        self.assertEqual(client_class.call_args.kwargs["base_url"], None)

    @patch("openai.OpenAI")
    def test_compatible_server_falls_back_to_json_mode(self, client_class):
        create = client_class.return_value.chat.completions.create
        create.side_effect = [bad_request(), openai_response("```json\n" + TRANSLATED + "\n```")]
        rows = t.call_openai([("m1", "hello")], "ja", openai_settings(openai_base_url="http://llm/v1"))
        self.assertEqual(rows["m1"]["text"], "[ja] hello")
        self.assertEqual(create.call_count, 2)
        self.assertEqual(create.call_args.kwargs["response_format"], {"type": "json_object"})
        self.assertEqual(client_class.call_args.kwargs["base_url"], "http://llm/v1")

    @patch("openai.OpenAI")
    def test_openai_bad_request_is_not_retried(self, client_class):
        create = client_class.return_value.chat.completions.create
        create.side_effect = bad_request()
        self.assertIsNone(t.call_openai([("m1", "hello")], "ja", openai_settings()))
        self.assertEqual(create.call_count, 1)

    @patch("openai.OpenAI")
    def test_refusal_and_truncation_give_nothing(self, client_class):
        create = client_class.return_value.chat.completions.create
        create.return_value = openai_response(None, refusal="I can't help with that.")
        self.assertIsNone(t.call_openai([("m1", "hello")], "ja", openai_settings()))
        create.return_value = openai_response('{"items": [', finish_reason="length")
        self.assertIsNone(t.call_openai([("m1", "hello")], "ja", openai_settings()))

    def test_missing_key_is_logged_not_raised(self):
        with patch.dict("os.environ", {}, clear=False) as env:
            env.pop("OPENAI_API_KEY", None)
            self.assertIsNone(t.call_openai([("m1", "hello")], "ja", openai_settings(openai_api_key=None)))

    @patch("openai.OpenAI")
    def test_exhausted_balance_is_logged_as_such(self, client_class):
        import httpx
        import openai

        response = httpx.Response(429, request=httpx.Request("POST", "http://test/v1/chat/completions"))
        error = openai.RateLimitError(
            "You have no credits remaining.", response=response, body={"code": "insufficient_quota"}
        )
        client_class.return_value.chat.completions.create.side_effect = error
        with patch("frappe.log_error") as log_error:
            self.assertIsNone(t.call_openai([("m1", "hello")], "ja", openai_settings()))
        self.assertIn("no credits left", log_error.call_args.kwargs["message"])
