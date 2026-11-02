import pytest

from app.services import llm
from app import config
from app.db.database import init_db

from app.api.auth import current_user
from app.main import app
from tests.constants import TEST_USER


@pytest.fixture(autouse=True)
def no_real_sleep(monkeypatch):
    """Make retries instant in every test."""
    real_run = llm.run_with_retry

    def fast_run(operation, **kwargs):
        return real_run(operation, sleep=lambda seconds: None, **kwargs)

    monkeypatch.setattr(llm, "run_with_retry", fast_run)




@pytest.fixture(autouse=True)
def isolated_database(monkeypatch, tmp_path):
    db_path = tmp_path.parent / f"{tmp_path.name}_test.db"
    monkeypatch.setattr(config, "DATABASE_PATH", db_path)
    init_db()

@pytest.fixture(autouse=True)
def signed_in_user():
    app.dependency_overrides[current_user] = lambda: TEST_USER
    yield TEST_USER
    app.dependency_overrides.clear()
