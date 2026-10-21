"""
db.py  -  the ONLY place that talks to MySQL.
Every screen calls db.fetch_all / db.execute, so connection handling is written once.
All values are passed as %s parameters (never glued into the SQL text) -> no SQL injection.
"""
from contextlib import contextmanager

import mysql.connector

import config


class Database:
    def __init__(self):
        self.conn = None

    # ----- connection -----
    def connect(self, with_database=True):
        cfg = config.load_db_config()
        if not with_database:
            cfg.pop("database")
        self.conn = mysql.connector.connect(connection_timeout=5, charset="utf8mb4", **cfg)
        self.conn.autocommit = True          # reads always see fresh data
        return self.conn

    def connection(self):
        if self.conn is None or not self.conn.is_connected():
            self.connect()
        return self.conn

    def close(self):
        try:
            if self.conn is not None:
                self.conn.close()
        except mysql.connector.Error:
            pass
        self.conn = None

    # ----- queries -----
    def fetch_all(self, sql, params=()):
        cur = self.connection().cursor(buffered=True)
        try:
            cur.execute(sql, params)
            return cur.fetchall()
        finally:
            cur.close()

    def fetch_one(self, sql, params=()):
        rows = self.fetch_all(sql, params)
        return rows[0] if rows else None

    def execute(self, sql, params=()):
        """INSERT / UPDATE / DELETE. Returns the new row id (if any)."""
        cur = self.connection().cursor(buffered=True)
        try:
            cur.execute(sql, params)
            return cur.lastrowid
        finally:
            cur.close()

    @contextmanager
    def transaction(self):
        """Several statements that must succeed together (used when saving a bill)."""
        conn = self.connection()
        conn.start_transaction()
        cur = conn.cursor(buffered=True)
        try:
            yield cur
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()


db = Database()      # one shared object for the whole application
