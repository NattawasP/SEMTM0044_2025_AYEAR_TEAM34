"""
DuckDB connection manager.
Creates views over Parquet files so SQL queries work like regular tables.
"""

import duckdb
from app.config import PARQUET


_conn: duckdb.DuckDBPyConnection | None = None


def get_connection() -> duckdb.DuckDBPyConnection:
    """Return a singleton DuckDB connection with Parquet views registered."""
    global _conn
    if _conn is not None:
        return _conn

    _conn = duckdb.connect(database=":memory:")

    # Register each Parquet file as a view
    for view_name, parquet_path in PARQUET.items():
        if parquet_path.exists():
            _conn.execute(
                f"CREATE VIEW {view_name} AS SELECT * FROM read_parquet('{parquet_path}')"
            )

    return _conn


def query(sql: str, params: list | None = None) -> list[dict]:
    """Execute SQL and return rows as list of dicts."""
    conn = get_connection()
    if params:
        result = conn.execute(sql, params)
    else:
        result = conn.execute(sql)
    columns = [desc[0] for desc in result.description]
    return [dict(zip(columns, row)) for row in result.fetchall()]


def query_df(sql: str, params: list | None = None):
    """Execute SQL and return a pandas DataFrame."""
    conn = get_connection()
    if params:
        return conn.execute(sql, params).fetchdf()
    return conn.execute(sql).fetchdf()
