import unittest

from flask import Flask

from ctf_platform.hoster import _challenge_request


class HosterChallengeRequestTests(unittest.TestCase):
    def test_strips_hoster_only_fields_before_ctfd_challenge_processing(self):
        app = Flask(__name__)
        with app.test_request_context(
            "/platform/hoster/challenges/new",
            method="POST",
            data={
                "name": "Example challenge",
                "type": "standard",
                "hoster_flags": "flag{example}",
                "nonce": "csrf-token",
            },
        ):
            challenge_request = _challenge_request()

        self.assertEqual(
            dict(challenge_request.form),
            {"name": "Example challenge", "type": "standard"},
        )


if __name__ == "__main__":
    unittest.main()
