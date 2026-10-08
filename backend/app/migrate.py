"""DB 테이블을 만든다 (마이그레이션). 로컬은 SQLite, DATABASE_URL 이 있으면 그 Postgres(Neon).

    python -m app.migrate          # backend/ 에서 실행

모델에 있는 7개 테이블을 없는 것만 만든다. 이미 있는 테이블과 데이터는 건드리지 않는다.
"""
from sqlalchemy import inspect

from . import config, models  # noqa: F401  (models: 테이블 등록)
from .db import Base, engine


def main() -> None:
    url = config.database_url()
    kind = "Postgres(Neon)" if url.startswith("postgresql") else "SQLite"
    before = set(inspect(engine).get_table_names())
    Base.metadata.create_all(engine)
    after = set(inspect(engine).get_table_names())
    print(f"대상: {kind}")
    print(f"새로 만든 테이블: {sorted(after - before) or '없음(이미 모두 있음)'}")
    print(f"현재 테이블({len(after)}): {sorted(after)}")
    missing = set(Base.metadata.tables) - after
    if missing:
        raise SystemExit(f"만들어지지 않은 테이블: {sorted(missing)}")


if __name__ == "__main__":
    main()
