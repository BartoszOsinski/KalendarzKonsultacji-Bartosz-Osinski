import pytest
from config import settings
from calendarproject.app import create_app
from calendarproject.extensions import db as _db

@pytest.fixture(scope="session")
def app():
    """
    Setup our flask test app, this only gets executed once.
    """
    params = {
        "DEBUG": False,
        "TESTING": True,
        "WTF_CSRF_ENABLED": False,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",  # In-memory SQLite
    }

    _app = create_app(settings_override=params)

    # Establish an application context before running the tests.
    ctx = _app.app_context()
    ctx.push()

    # Create all tables
    _db.create_all()

    yield _app

    # Clean up
    _db.session.remove()
    _db.drop_all()
    ctx.pop()

@pytest.fixture(scope="function")
def client(app):
    """
    Setup an app client, this gets executed for each test function.
    """
    # Use yield instead of with context manager to avoid request context errors
    client = app.test_client()
    yield client

@pytest.fixture(scope="function")
def db(app):
    """
    Reset database between tests
    """
    # Clear all tables
    for table in reversed(_db.metadata.sorted_tables):
        _db.session.execute(table.delete())

    _db.session.commit()
    return _db