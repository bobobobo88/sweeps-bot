import sqlite3
from typing import Optional
from contextlib import closing

def get_db(path="data.db"):
    conn = sqlite3.connect(path)
    conn.execute("""CREATE TABLE IF NOT EXISTS posts (
      id TEXT PRIMARY KEY,
      url TEXT,
      title TEXT,
      deadline_utc TEXT,
      created_at_utc TEXT DEFAULT CURRENT_TIMESTAMP
    )""")
    return conn

def seen(conn, pid: str) -> bool:
    with closing(conn.cursor()) as cur:
        cur.execute("SELECT 1 FROM posts WHERE id=?", (pid,))
        return cur.fetchone() is not None

def save(conn, pid: str, url: str, title: str, deadline_iso: Optional[str]):
    with closing(conn.cursor()) as cur:
        cur.execute(
            "INSERT OR IGNORE INTO posts (id,url,title,deadline_utc) VALUES (?,?,?,?)",
            (pid, url, title, deadline_iso)
        )
        conn.commit()
