import pymysql
from pymysql.cursors import DictCursor
from flask import current_app, g

def get_db():
    """Returns a thread-safe / request-safe PyMySQL database connection."""
    if 'db' not in g:
        g.db = pymysql.connect(
            host=current_app.config['MYSQL_HOST'],
            port=current_app.config['MYSQL_PORT'],
            user=current_app.config['MYSQL_USER'],
            password=current_app.config['MYSQL_PASSWORD'],
            database=current_app.config['MYSQL_DB'],
            cursorclass=DictCursor,
            autocommit=False,
            charset='utf8mb4'
        )
    return g.db

def close_db(e=None):
    """Closes the database connection at the end of the request."""
    db = g.pop('db', None)
    if db is not None:
        db.close()

def query_db(query, args=(), one=False, commit=False):
    """Convenience helper to query the database with parameterized inputs."""
    db = get_db()
    with db.cursor() as cur:
        cur.execute(query, args)
        if commit:
            db.commit()
            return cur.lastrowid
        rv = cur.fetchall()
        return (rv[0] if rv else None) if one else rv

def init_app(app):
    """Register database teardown hook."""
    app.teardown_appcontext(close_db)
