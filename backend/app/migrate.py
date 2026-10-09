from alembic.config import Config
from sqlalchemy.engine import Engine

from alembic import command
from app.config import BACKEND_DIR


def alembic_config() -> Config:
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    return cfg


def _run(engine: Engine, fn: str, revision: str) -> None:
    cfg = alembic_config()
    with engine.begin() as conn:
        cfg.attributes["connection"] = conn
        getattr(command, fn)(cfg, revision)


def upgrade_to_head(engine: Engine) -> None:
    _run(engine, "upgrade", "head")


def downgrade_to_base(engine: Engine) -> None:
    _run(engine, "downgrade", "base")
