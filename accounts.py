"""Manage locally provisioned accounts and browser sessions."""

from contextlib import closing
import hashlib
import hmac
from pathlib import Path
import re
import secrets
import sqlite3
from threading import BoundedSemaphore
import time
from uuid import uuid4


DATA_DIR = Path(__file__).resolve().parent / 'local_data'
REMEMBER_SECONDS = 30 * 24 * 60 * 60
SESSION_SECONDS = 12 * 60 * 60
ATTEMPT_WINDOW = 5 * 60
MAX_ATTEMPTS = 10
USERNAME = re.compile(r'[a-zA-Z0-9_-]{1,32}')
SESSION_TOKEN = re.compile(r'[a-zA-Z0-9_-]{43}')


class LoginBusy(Exception):
    """Too many recent or concurrent sign-in attempts."""


def password_hash(password, salt):
    return hashlib.scrypt(password.encode('utf-8'), salt=salt, n=2**15, r=8, p=3,
                          maxmem=64 * 1024 * 1024, dklen=32)


def session_hash(token):
    return hashlib.sha256(token.encode('ascii')).digest()


def write_token(token):
    return hashlib.sha256(b'planner-write:' + token.encode('ascii')).hexdigest()


class Accounts:
    def __init__(self, directory=DATA_DIR):
        self.directory = directory
        self.path = directory / 'accounts.sqlite3'
        self.login_slot = BoundedSemaphore()

    def connect(self):
        db = sqlite3.connect(self.path)
        db.execute('PRAGMA foreign_keys = ON')
        return db

    def initialize(self):
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        try:
            self.path.touch(mode=0o600, exist_ok=False)
        except FileExistsError:
            pass
        with closing(self.connect()) as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY, username TEXT NOT NULL COLLATE NOCASE UNIQUE,
                    salt BLOB NOT NULL, password_hash BLOB NOT NULL
                );
                CREATE TABLE IF NOT EXISTS sessions (
                    digest BLOB PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users (id),
                    expires INTEGER NOT NULL
                );
                CREATE INDEX IF NOT EXISTS sessions_by_user ON sessions (user_id);
                CREATE TABLE IF NOT EXISTS login_attempts (
                    id INTEGER PRIMARY KEY, attempted INTEGER NOT NULL
                );
            """)

    def user_id(self, username):
        with closing(self.connect()) as db:
            row = db.execute('SELECT id FROM users WHERE username = ?', (username,)).fetchone()
            return row[0] if row else None

    def planner_path(self, user_id):
        return self.directory / 'users' / user_id / 'planner.json'

    def set_password(self, username, password, *, create):
        if not USERNAME.fullmatch(username):
            raise ValueError('Use 1 to 32 letters, digits, underscores or hyphens for the username.')
        if not 12 <= len(password) <= 256:
            raise ValueError('Choose a passphrase between 12 and 256 characters.')
        salt = secrets.token_bytes(16)
        digest = password_hash(password, salt)
        with closing(self.connect()) as db, db:
            if create:
                try:
                    db.execute('INSERT INTO users VALUES (?, ?, ?, ?)',
                               (uuid4().hex, username, salt, digest))
                except sqlite3.IntegrityError:
                    raise ValueError('That username already exists.') from None
            else:
                db.execute('BEGIN IMMEDIATE')
                user = db.execute('SELECT id FROM users WHERE username = ?', (username,)).fetchone()
                if not user:
                    raise ValueError('That username does not exist.')
                db.execute('UPDATE users SET salt = ?, password_hash = ? WHERE id = ?',
                           (salt, digest, user[0]))
                db.execute('DELETE FROM sessions WHERE user_id = ?', user)

    def login(self, username, password, remember):
        if not USERNAME.fullmatch(username) or not 1 <= len(password) <= 256:
            return None
        if not self.login_slot.acquire(blocking=False):
            raise LoginBusy
        try:
            return self.verify_and_issue(username, password, remember)
        finally:
            self.login_slot.release()

    def verify_and_issue(self, username, password, remember):
        now = int(time.time())
        with closing(self.connect()) as db:
            with db:
                db.execute('DELETE FROM login_attempts WHERE attempted <= ?', (now - ATTEMPT_WINDOW,))
                if db.execute('SELECT COUNT(*) FROM login_attempts').fetchone()[0] >= MAX_ATTEMPTS:
                    raise LoginBusy
                attempt = db.execute('INSERT INTO login_attempts (attempted) VALUES (?)', (now,)).lastrowid
                row = db.execute('SELECT id, salt, password_hash FROM users WHERE username = ?',
                                 (username,)).fetchone()
            salt = row[1] if row else bytes(16)
            digest = password_hash(password, salt)
            if not hmac.compare_digest(digest, row[2] if row else bytes(32)) or not row:
                return None
            token = secrets.token_urlsafe(32)
            seconds = REMEMBER_SECONDS if remember else SESSION_SECONDS
            with db:
                db.execute('DELETE FROM sessions WHERE expires <= ?', (now,))
                db.execute('DELETE FROM login_attempts WHERE id = ?', (attempt,))
                # A reset may have replaced the password while scrypt was running.
                inserted = db.execute(
                    'INSERT INTO sessions SELECT ?, id, ? FROM users WHERE id = ? AND password_hash = ?',
                    (session_hash(token), now + seconds, row[0], row[2]),
                )
                return token if inserted.rowcount else None

    def session_user(self, token):
        if not SESSION_TOKEN.fullmatch(token):
            return None
        with closing(self.connect()) as db:
            row = db.execute(
                'SELECT users.id, users.username FROM sessions JOIN users ON users.id = sessions.user_id '
                'WHERE sessions.digest = ? AND sessions.expires > ?',
                (session_hash(token), int(time.time())),
            ).fetchone()
            return row

    def sign_out(self, token):
        if SESSION_TOKEN.fullmatch(token):
            with closing(self.connect()) as db, db:
                db.execute('DELETE FROM sessions WHERE digest = ?', (session_hash(token),))
