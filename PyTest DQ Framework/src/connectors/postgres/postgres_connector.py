"""PostgreSQL connector used by the DQ framework."""

import pandas as pd
import psycopg2


class PostgresConnectorContextManager:
    """
    Context manager that owns one PostgreSQL connection.

    Usage::

        with PostgresConnectorContextManager(db_user=..., db_password=..., db_host=...,
                                             db_name=..., db_port=...) as db:
            df = db.get_data_sql("select 1 as one")

    The session is opened read-only: DQ checks must never modify the source data.
    """

    def __init__(self, db_user: str, db_password: str, db_host: str = "localhost",
                 db_name: str = "mydatabase", db_port=5434, connect_timeout: int = 10):
        self.db_user = db_user
        self.db_password = db_password
        self.db_host = db_host
        self.db_name = db_name
        self.db_port = int(db_port)
        self.connect_timeout = connect_timeout
        self._connection = None

    def __enter__(self):
        self._connection = psycopg2.connect(
            user=self.db_user,
            password=self.db_password,
            host=self.db_host,
            dbname=self.db_name,
            port=self.db_port,
            connect_timeout=self.connect_timeout,
        )
        self._connection.set_session(readonly=True, autocommit=True)
        return self

    def __exit__(self, exc_type, exc_value, exc_tb):
        if self._connection is not None:
            self._connection.close()
            self._connection = None
        return False  # never swallow exceptions

    def get_data_sql(self, sql: str) -> pd.DataFrame:
        """Execute ``sql`` and return the result set as a pandas DataFrame."""
        if self._connection is None:
            raise RuntimeError("Connection is not open: use PostgresConnectorContextManager in a 'with' block.")
        with self._connection.cursor() as cursor:
            cursor.execute(sql)
            columns = [column.name for column in cursor.description]
            rows = cursor.fetchall()
        return pd.DataFrame(rows, columns=columns)
