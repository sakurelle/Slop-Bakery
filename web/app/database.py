from contextlib import contextmanager

from psycopg import connect, sql
from psycopg.rows import dict_row

from .config import get_settings


def _connection_kwargs() -> dict:
    settings = get_settings()
    return {
        "host": settings.db_host,
        "port": settings.db_port,
        "dbname": settings.db_name,
        "user": settings.db_user,
        "password": settings.db_password,
        "row_factory": dict_row,
    }


def apply_audit_context(conn, user_id=None, user_ip=None) -> None:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT set_config('app.current_user_id', %s, false)",
            ("" if user_id is None else str(user_id),),
        )
        cur.execute(
            "SELECT set_config('app.current_user_ip', %s, false)",
            ("" if user_ip is None else str(user_ip),),
        )


@contextmanager
def get_db(user_id=None, user_ip=None):
    conn = connect(**_connection_kwargs())
    try:
        apply_audit_context(conn, user_id=user_id, user_ip=user_ip)
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def fetch_all(query: str, params=None, user_id=None, user_ip=None):
    with get_db(user_id=user_id, user_ip=user_ip) as conn:
        with conn.cursor() as cur:
            cur.execute(query, params or ())
            return cur.fetchall()


def fetch_one(query: str, params=None, user_id=None, user_ip=None):
    with get_db(user_id=user_id, user_ip=user_ip) as conn:
        with conn.cursor() as cur:
            cur.execute(query, params or ())
            return cur.fetchone()


def fetch_value(query: str, params=None, user_id=None, user_ip=None):
    row = fetch_one(query, params=params, user_id=user_id, user_ip=user_ip)
    if not row:
        return None
    return next(iter(row.values()))


def execute(query: str, params=None, user_id=None, user_ip=None) -> int:
    with get_db(user_id=user_id, user_ip=user_ip) as conn:
        with conn.cursor() as cur:
            cur.execute(query, params or ())
            return cur.rowcount


def next_id(conn, table_name: str, id_column: str) -> int:
    statement = sql.SQL("SELECT COALESCE(MAX({id_column}) + 1, 1) AS next_id FROM {table_name}").format(
        id_column=sql.Identifier(id_column),
        table_name=sql.Identifier(table_name),
    )
    with conn.cursor() as cur:
        cur.execute(statement)
        row = cur.fetchone()
        return row["next_id"]
