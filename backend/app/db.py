"""SQLite storage for farmer accounts."""
import os
import sqlite3
from flask import current_app,g
SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 user_id TEXT NOT NULL UNIQUE,
 name TEXT NOT NULL,
 phone TEXT NOT NULL UNIQUE,
 password_hash TEXT NOT NULL,
 created_at TEXT NOT NULL
);
"""
def init_db(path):
 os.makedirs(os.path.dirname(os.path.abspath(path)),exist_ok=True)
 conn=sqlite3.connect(path)
 try: conn.executescript(SCHEMA);conn.commit()
 finally:conn.close()
def get_db():
 if "db" not in g:
  g.db=sqlite3.connect(current_app.config["DATABASE"]);g.db.row_factory=sqlite3.Row
 return g.db
def close_db(_error=None):
 db=g.pop("db",None)
 if db is not None:db.close()
