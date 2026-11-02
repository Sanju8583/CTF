import unittest
from unittest.mock import patch

from flask import Flask
from werkzeug.exceptions import Forbidden

from ctf_platform.roles import hosters_or_admins_only, platform_admins_only


class RoleDecoratorTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.secret_key = "test"
        self.app.add_url_rule(
            "/login", endpoint="auth.login", view_func=lambda: "login"
        )

    def test_hoster_can_access_limited_hoster_route(self):
        @hosters_or_admins_only
        def endpoint():
            return "allowed"

        with self.app.test_request_context("/hoster"):
            with patch("ctf_platform.roles.is_admin", return_value=False), patch(
                "ctf_platform.roles.is_hoster", return_value=True
            ):
                self.assertEqual(endpoint(), "allowed")

    def test_participant_cannot_access_hoster_route(self):
        @hosters_or_admins_only
        def endpoint():
            return "allowed"

        with self.app.test_request_context("/hoster"):
            with patch("ctf_platform.roles.is_admin", return_value=False), patch(
                "ctf_platform.roles.is_hoster", return_value=False
            ), patch("ctf_platform.roles.authed", return_value=True):
                with self.assertRaises(Forbidden):
                    endpoint()

    def test_hoster_does_not_get_admin_role_management_access(self):
        @platform_admins_only
        def endpoint():
            return "allowed"

        with self.app.test_request_context("/admin/roles"):
            with patch("ctf_platform.roles.is_admin", return_value=False), patch(
                "ctf_platform.roles.authed", return_value=True
            ):
                with self.assertRaises(Forbidden):
                    endpoint()

    def test_anonymous_hoster_route_redirects_to_login(self):
        @hosters_or_admins_only
        def endpoint():
            return "allowed"

        with self.app.test_request_context("/hoster"):
            with patch("ctf_platform.roles.is_admin", return_value=False), patch(
                "ctf_platform.roles.is_hoster", return_value=False
            ), patch("ctf_platform.roles.authed", return_value=False):
                response = endpoint()
                self.assertEqual(response.status_code, 302)
                self.assertIn("/login", response.location)


if __name__ == "__main__":
    unittest.main()
