"""Application smoke tests.

These tests exercise the Flask application without relying on optional
third-party dependencies that are unavailable in the execution
environment (notably ``flask_sqlalchemy``).  To keep the production
code untouched, we provide a lightweight stub that mimics just enough of
the ``flask_sqlalchemy`` API for the parts of the app that our tests
touch.  When the real dependency is installed (for example in
production or in CI) the stub is ignored and the genuine extension is
used.
"""

from __future__ import annotations

import sys
import types
import unittest
from typing import Any, Optional


def _install_flask_sqlalchemy_stub() -> None:
    """Install a minimal ``flask_sqlalchemy`` stub if it is unavailable."""

    if "flask_sqlalchemy" in sys.modules:
        # The real dependency is available – nothing to do.
        return

    fake_module = types.ModuleType("flask_sqlalchemy")

    class _FakeQuery:
        """Very small stand-in for SQLAlchemy's query interface."""

        def filter_by(self, **_: Any) -> "_FakeQuery":
            return self

        def all(self) -> list[Any]:
            return []

        def first(self) -> Optional[Any]:
            return None

        def get(self, *_: Any, **__: Any) -> Optional[Any]:
            return None

        def get_or_404(self, *_: Any, **__: Any) -> None:
            raise LookupError("Object not found")

    class _FakeSession:
        def add(self, *_: Any, **__: Any) -> None:  # pragma: no cover - trivial
            pass

        def commit(self) -> None:  # pragma: no cover - trivial
            pass

        def remove(self) -> None:  # pragma: no cover - trivial
            pass

    class _FakeColumn:
        def __init__(self, *_: Any, **__: Any) -> None:  # pragma: no cover - trivial
            pass

    class _FakeType:
        def __init__(self, *_: Any, **__: Any) -> None:  # pragma: no cover - trivial
            pass

    def _fake_relationship(*_: Any, **__: Any) -> list[Any]:  # pragma: no cover - trivial
        return []

    def _fake_backref(name: str, **_: Any) -> str:  # pragma: no cover - trivial
        return name

    def _fake_foreign_key(*_: Any, **__: Any) -> None:  # pragma: no cover - trivial
        return None

    class SQLAlchemy:  # pragma: no cover - trivial container of helpers
        Column = _FakeColumn
        Integer = _FakeType
        String = _FakeType
        Boolean = _FakeType
        DateTime = _FakeType
        Text = _FakeType

        def __init__(self, *_: Any, **__: Any) -> None:
            self.session = _FakeSession()
            self.Model = type("Model", (), {"query": _FakeQuery()})

        def create_all(self) -> None:
            pass

        def drop_all(self) -> None:
            pass

        def relationship(self, *_: Any, **__: Any) -> list[Any]:
            return _fake_relationship()

        def backref(self, name: str, **_: Any) -> str:
            return _fake_backref(name)

        def ForeignKey(self, *_: Any, **__: Any) -> None:
            return _fake_foreign_key()

    fake_module.SQLAlchemy = SQLAlchemy
    fake_module.Column = _FakeColumn
    fake_module.Integer = _FakeType
    fake_module.String = _FakeType
    fake_module.Boolean = _FakeType
    fake_module.DateTime = _FakeType
    fake_module.Text = _FakeType
    fake_module.relationship = _fake_relationship
    fake_module.backref = _fake_backref
    fake_module.ForeignKey = _fake_foreign_key

    sys.modules["flask_sqlalchemy"] = fake_module


_install_flask_sqlalchemy_stub()

from app import app, db


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
