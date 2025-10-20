"""Application smoke tests that can run without optional dependencies."""

from __future__ import annotations

import unittest
from datetime import datetime, timedelta
from typing import Any, Optional, cast

from werkzeug.security import generate_password_hash

from tests.flask_sqlalchemy_stub import ensure_stub

# Ensure the optional ``flask_sqlalchemy`` dependency is stubbed before the app
# module is imported.  In production environments the real package is
# installed, so the stub simply detects it and exits early.
ensure_stub()

from app import User, app, db  # noqa: E402
from sqlalchemy.orm import Session, scoped_session  # noqa: E402


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
            scoped = cast("scoped_session[Session]", db.session)
            scoped.remove()
            db.drop_all()

    def test_index_redirects_to_login(self) -> None:
        response = self.app.get("/")
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.headers["Location"].endswith("/login"))

    def _get_csrf_token(self, path: str) -> str:
        self.app.get(path)
        with self.app.session_transaction() as session_data:
            token: Any = session_data["_csrf_token"]
            if not isinstance(token, str):
                raise AssertionError("Missing CSRF token in session")
            return token

    def _create_user(
        self,
        email: str,
        password: str,
        *,
        is_admin: bool = False,
        is_active: bool = False,
        payment_verified: bool = False,
        subscription_end: Optional[datetime] = None,
    ) -> User:
        with app.app_context():
            user = User(
                email=email,
                password=generate_password_hash(password),
                is_admin=is_admin,
                is_active=is_active,
                payment_verified=payment_verified,
                subscription_start=datetime.utcnow() if payment_verified else None,
                subscription_end=subscription_end,
            )
            db.session.add(user)
            db.session.commit()
            return user

    def test_inactive_user_cannot_login(self) -> None:
        self._create_user("pending@speedmail.com", "secret")
        token = self._get_csrf_token("/login")
        response = self.app.post(
            "/login",
            data={
                "email": "pending@speedmail.com",
                "password": "secret",
                "csrf_token": token,
            },
            follow_redirects=True,
        )
        self.assertIn(b"Your account is not active.", response.data)

    def test_admin_route_requires_admin_privileges(self) -> None:
        self._create_user(
            "user@speedmail.com",
            "secret",
            is_active=True,
            payment_verified=True,
            subscription_end=datetime.utcnow() + timedelta(days=30),
        )
        token = self._get_csrf_token("/login")
        login_response = self.app.post(
            "/login",
            data={
                "email": "user@speedmail.com",
                "password": "secret",
                "csrf_token": token,
            },
        )
        self.assertEqual(login_response.status_code, 302)
        admin_response = self.app.get("/admin/pending")
        self.assertEqual(admin_response.status_code, 403)

    def test_admin_can_view_pending_users(self) -> None:
        self._create_user(
            "admin@speedmail.com",
            "secret",
            is_admin=True,
            is_active=True,
            payment_verified=True,
            subscription_end=datetime.utcnow() + timedelta(days=30),
        )
        token = self._get_csrf_token("/login")
        self.app.post(
            "/login",
            data={
                "email": "admin@speedmail.com",
                "password": "secret",
                "csrf_token": token,
            },
        )
        response = self.app.get("/admin/pending")
        self.assertEqual(response.status_code, 200)


if __name__ == "__main__":
    unittest.main()
