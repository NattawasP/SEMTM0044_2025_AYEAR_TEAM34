"""
DuckDB connection manager.
Creates views over Parquet files so SQL queries work like regular tables.

Thread-safety: FastAPI runs sync endpoints in a thread pool, so multiple
threads may query DuckDB concurrently. We use conn.cursor() per query call
to avoid conflicts on the shared connection.
"""

import threading

import duckdb
from app.config import PARQUET


_conn: duckdb.DuckDBPyConnection | None = None
_init_lock = threading.Lock()


def get_connection() -> duckdb.DuckDBPyConnection:
    """Return a singleton DuckDB connection with Parquet views registered."""
    global _conn
    if _conn is not None:
        return _conn

    with _init_lock:
        # Double-check after acquiring lock
        if _conn is not None:
            return _conn

        _conn = duckdb.connect(database=":memory:")

        # Tune for low-memory environments (e.g. small EC2)
        _conn.execute("SET memory_limit='512MB'")
        _conn.execute("SET threads=2")
        _conn.execute("SET preserve_insertion_order=false")

        # Register each Parquet file as a view
        for view_name, parquet_path in PARQUET.items():
            if parquet_path.exists():
                _conn.execute(
                    f"CREATE VIEW {view_name} AS SELECT * FROM read_parquet('{parquet_path}')"
                )

    return _conn


def query(sql: str, params: list | None = None) -> list[dict]:
    """Execute SQL and return rows as list of dicts (thread-safe via cursor)."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        if params:
            result = cursor.execute(sql, params)
        else:
            result = cursor.execute(sql)
        columns = [desc[0] for desc in result.description]
        return [dict(zip(columns, row)) for row in result.fetchall()]
    finally:
        cursor.close()


def query_df(sql: str, params: list | None = None):
    """Execute SQL and return a pandas DataFrame (thread-safe via cursor)."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        if params:
            return cursor.execute(sql, params).fetchdf()
        return cursor.execute(sql).fetchdf()
    finally:
        cursor.close()
