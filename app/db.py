from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.types import JSON, TypeDecorator


class JSONB(TypeDecorator):
    """Кросс-БД JSON: jsonb на PostgreSQL, JSON на остальных (тесты на SQLite).

    Соответствие спеке §6 (jsonb) + работоспособность в тестах на SQLite.
    """

    impl = JSON
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            from sqlalchemy.dialects.postgresql import JSONB as PG_JSONB

            return dialect.type_descriptor(PG_JSONB())
        return dialect.type_descriptor(JSON())


class Base(DeclarativeBase):
    pass
