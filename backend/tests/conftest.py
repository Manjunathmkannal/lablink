"""
Shared pytest fixtures for all backend tests.
Uses mongomock – no real MongoDB required.
"""
import pytest
import mongomock
from unittest.mock import patch, MagicMock


def _make_test_app(mock_db):
    """
    Create a Flask test application with all mongo.db calls redirected
    to a mongomock database.

    Strategy: patch the single shared `app.extensions.mongo` object (which is
    the one imported by all services and routes), then also patch any module
    that imports `mongo` directly under its own namespace so that module-level
    `mongo.db` calls also resolve to the mock.
    """
    # Patch PyMongo.init_app so the factory doesn't try to connect to MongoDB
    with patch("flask_pymongo.PyMongo.init_app"):
        from app import create_app
        app = create_app(
            {
                "TESTING": True,
                "SECRET_KEY": "test-secret-key-long-enough-32ch",
                "CORS_ORIGIN": "*",
            }
        )

    # Modules that import `mongo` at module level and use `mongo.db`
    # Note: routes that import from extensions get the same object, so
    # patching extensions.mongo is sufficient for most. We also patch
    # direct imports in services to cover all code paths.
    targets = [
        "app.extensions.mongo",
        "app.routes.auth.mongo",
        "app.routes.notifications.mongo",
        "app.routes.equipment.mongo",
        "app.routes.bookings.mongo",
        "app.routes.faculty.mongo",
        "app.routes.admin.mongo",
        "app.routes.lab_assistant.mongo",
        "app.routes.projects.mongo",
        "app.routes.ai.mongo",
        "app.services.auth_service.mongo",
        "app.utils.jwt_utils.mongo",
        "app.services.booking_service.mongo",
        "app.services.notification_service.mongo",
        "app.services.equipment_service.mongo",
        "app.services.project_service.mongo",
    ]

    patchers = []
    for target in targets:
        p = patch(target)
        try:
            mock = p.start()
            mock.db = mock_db
            patchers.append(p)
        except AttributeError:
            # Module doesn't have this attribute; skip safely
            pass

    yield app

    for p in patchers:
        p.stop()


@pytest.fixture()
def mock_db():
    """Return a fresh in-memory mongomock database for each test."""
    client = mongomock.MongoClient()
    return client["lablink_test"]


@pytest.fixture()
def app(mock_db):
    yield from _make_test_app(mock_db)


@pytest.fixture()
def client(app, mock_db):
    return app.test_client(), mock_db
