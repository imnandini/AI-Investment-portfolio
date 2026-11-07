"""Exercise upgrade/downgrade in a newly created, isolated PostgreSQL schema."""
from pathlib import Path
import re
import sys
from uuid import uuid4
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from app.core.config import Settings


schema = "copilot_migration_test_" + uuid4().hex
assert re.fullmatch(r"copilot_migration_test_[a-f0-9]{32}", schema)
engine = create_engine(Settings().database_url)
with engine.connect() as connection:
    connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    connection.commit()
    try:
        connection.execute(text(f'SET search_path TO "{schema}", public'))
        connection.commit()
        cfg = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
        cfg.attributes["connection"] = connection
        cfg.attributes["version_table_schema"] = schema
        cfg.attributes["include_object"] = lambda obj, name, kind, reflected, compare: not (kind == "table" and name == "alembic_version")
        original_default_schema = connection.dialect.default_schema_name
        connection.dialect.default_schema_name = schema
        command.upgrade(cfg, "head")
        connection.commit()
        assert "document_chunks" in inspect(connection).get_table_names(schema=schema)
        command.downgrade(cfg, "0002_instrument_sector")
        connection.commit()
        assert "document_chunks" not in inspect(connection).get_table_names(schema=schema)
        command.upgrade(cfg, "head")
        connection.commit()
        assert "document_chunks" in inspect(connection).get_table_names(schema=schema)
        command.check(cfg)
        print("Isolated PostgreSQL schema: upgrade, downgrade, re-upgrade and model check passed.")
    finally:
        connection.rollback()
        connection.dialect.default_schema_name = original_default_schema
        connection.execute(text('SET search_path TO public'))
        # The validated name refers only to the temporary schema created above.
        connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        connection.commit()
engine.dispose()
