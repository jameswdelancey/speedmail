"""Application smoke tests that can run without optional dependencies."""

from __future__ import annotations

import unittest

from tests.flask_sqlalchemy_stub import ensure_stub

# Ensure the optional ``flask_sqlalchemy`` dependency is stubbed before the app
# module is imported.  In production environments the real package is
# installed, so the stub simply detects it and exits early.
ensure_stub()

from app import app, db  # noqa: E402


class AppTestCase(unittest.TestCase):
    def setUp(self) -> None:
        app.config["TESTING"] = True
        app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
        app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

        self.app = app.test_client()
        with app.app_context():
            db.create_all()

    def tearDown(self) -> None:
        with app.app_context():
            db.session.remove()
            db.drop_all()

    def test_index_redirects_to_login(self) -> None:
        response = self.app.get("/")
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.headers["Location"].endswith("/login"))


if __name__ == "__main__":
    unittest.main()
