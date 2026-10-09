from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings
from app.db import make_engine
from app.migrate import downgrade_to_base, upgrade_to_head
from app.seed import seed_properties

FIXTURES = Path(__file__).parent / "fixtures"


def _db_identity(url: str) -> tuple[str | None, str | None]:
    u = make_url(url)
    host = (u.host or "").replace("-pooler.", ".")
    return host, u.database


@pytest.fixture(scope="session")
def engine() -> Iterator[Engine]:
    settings = get_settings()
    url = settings.test_database_url
    if not url:
        pytest.exit(
            "TEST_DATABASE_URL is not set. Point it at a throwaway Postgres database "
            "(e.g. a Neon branch or a separate database); see README.",
            returncode=2,
        )
    main_ids = {_db_identity(settings.database_url)}
    if settings.direct_database_url:
        main_ids.add(_db_identity(settings.direct_database_url))
    if _db_identity(url) in main_ids:
        pytest.exit("TEST_DATABASE_URL points at the main database; refusing to run.", 2)

    eng = make_engine(url)
    # Prove migrations are reproducible from an empty schema on every test session.
    downgrade_to_base(eng)
    upgrade_to_head(eng)
    with Session(eng) as s:
        seed_properties(s)
    yield eng
    eng.dispose()


@pytest.fixture
def db(engine: Engine) -> Iterator[Session]:
    """Session inside an outer transaction that is rolled back after the test.

    Code under test may call commit()/rollback(); those act on savepoints only.
    """
    conn = engine.connect()
    outer = conn.begin()
    session = Session(
        bind=conn,
        autoflush=False,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )
    try:
        yield session
    finally:
        session.close()
        outer.rollback()
        conn.close()


@pytest.fixture
def session_factory(engine: Engine) -> Iterator[sessionmaker[Session]]:
    """Real committing sessions (for concurrency tests). Review/run tables are wiped after."""
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    yield factory
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE reviews, collection_runs RESTART IDENTITY"))
