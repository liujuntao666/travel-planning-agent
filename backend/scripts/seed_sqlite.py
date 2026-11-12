"""把 deploy/mysql/init/02_init_data.sql 的 INSERT 语句导入 SQLite，便于没有 MySQL 时本地演示。

用法（在 backend 目录下）：
    DATABASE_URL=sqlite:///./var/dev.db python scripts/seed_sqlite.py
"""

import sys
from pathlib import Path

from sqlalchemy import text

BACKEND_DIR = Path(__file__).resolve().parents[1]
ROOT_DIR = BACKEND_DIR.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.common.db import engine, init_db  # noqa: E402


def split_statements(sql: str) -> list[str]:
    statements: list[str] = []
    buf: list[str] = []
    quote: str | None = None
    i = 0
    while i < len(sql):
        ch = sql[i]
        if quote:
            buf.append(ch)
            if ch == "\\" and i + 1 < len(sql):
                buf.append(sql[i + 1])
                i += 2
                continue
            if ch == quote:
                quote = None
            i += 1
            continue
        if ch in "'\"":
            quote = ch
            buf.append(ch)
            i += 1
            continue
        if ch == "-" and sql.startswith("--", i):
            newline = sql.find("\n", i)
            i = len(sql) if newline == -1 else newline
            continue
        if ch == ";":
            statement = "".join(buf).strip()
            if statement:
                statements.append(statement)
            buf = []
            i += 1
            continue
        buf.append(ch)
        i += 1
    tail = "".join(buf).strip()
    if tail:
        statements.append(tail)
    return statements


def main() -> None:
    if not engine.url.get_backend_name() == "sqlite":
        raise SystemExit(f"仅用于 SQLite，当前 DATABASE_URL={engine.url}")

    init_db()
    sql = (ROOT_DIR / "deploy" / "mysql" / "init" / "02_init_data.sql").read_text(encoding="utf-8")
    statements = [
        s for s in split_statements(sql) if s.lstrip().upper().startswith("INSERT")
    ]
    with engine.begin() as conn:
        for statement in statements:
            conn.exec_driver_sql(statement.replace("`", ""))
    print(f"已导入 {len(statements)} 条 INSERT 到 {engine.url}")


if __name__ == "__main__":
    main()
