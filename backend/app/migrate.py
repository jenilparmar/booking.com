from alembic import command
from alembic.config import Config
from sqlalchemy.engine import Engine

from app.config import BACKEND_DIR


def alembic_config(url: str) -> Config:
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    cfg.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    return cfg


def upgrade_to_head(engine: Engine) -> None:
    cfg = alembic_config(engine.url.render_as_string(hide_password=False))
    with engine.begin() as conn:
        cfg.attributes["connection"] = conn
        command.upgrade(cfg, "head")
