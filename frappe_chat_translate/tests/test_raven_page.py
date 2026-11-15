"""The translation script is added to Raven's page only."""

from unittest.mock import patch

import frappe
from werkzeug.wrappers import Request, Response

try:
    from frappe.tests import IntegrationTestCase
except ImportError:  # Frappe v15
    from frappe.tests.utils import FrappeTestCase as IntegrationTestCase

from frappe_chat_translate import raven_page

PAGE = "<html><body><div id='root'></div></body></html>"


def run(path, body=PAGE, mimetype="text/html", status=200):
    request = Request.from_values(path=path)
    response = Response(body, mimetype=mimetype, status=status)
    raven_page.add_translation_script(response=response, request=request)
    return response.get_data(as_text=True)


class TestRavenPage(IntegrationTestCase):
    def setUp(self):
        frappe.set_user("Administrator")

    def test_added_to_raven_page_and_client_routes(self):
        for path in ("/raven", "/raven/channel/general"):
            html = run(path)
            self.assertIn("raven_translate.js", html)
            self.assertTrue(html.index("raven_translate.js") < html.index("</body>"))

    def test_added_once(self):
        html = run("/raven", body=run("/raven"))
        self.assertEqual(html.count("raven_translate.js"), 1)

    def test_other_pages_and_responses_untouched(self):
        self.assertEqual(run("/app"), PAGE)
        self.assertEqual(run("/ravenous"), PAGE)
        self.assertEqual(run("/raven", mimetype="application/json"), PAGE)
        self.assertEqual(run("/raven", status=404), PAGE)

    def test_guest_untouched(self):
        with patch.object(frappe.session, "user", "Guest"):
            self.assertEqual(run("/raven"), PAGE)
