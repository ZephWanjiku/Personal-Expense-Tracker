"""
database.py
Handles all database setup and CRUD operations for the Personal Expense Tracker.
Now supports multiple users: every category, transaction, and budget belongs to
a user_id, and all queries are scoped to the current user.

Uses SQLite by default. Swap DB_PATH / connection logic for PostgreSQL if needed
(see README).
"""

import sqlite3
from contextlib import contextmanager

import auth

DB_PATH = "expense_tracker.db"

DEFAULT_CATEGORIES = [
    ("Salary", "income"),
    ("Freelance", "income"),
    ("Investments", "income"),
    ("Other Income", "income"),
    ("Food", "expense"),
    ("Rent", "expense"),
    ("Transport", "expense"),
    ("Utilities", "expense"),
    ("Entertainment", "expense"),
    ("Health", "expense"),
    ("Shopping", "expense"),
    ("Other Expense", "expense"),
]


@contextmanager
def get_connection():
    """Context manager that yields a SQLite connection with foreign keys enabled."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    """Create tables if they don't exist and migrate the old single-user schema."""
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                type TEXT NOT NULL CHECK (type IN ('income', 'expense')),
                UNIQUE(user_id, name),
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                date TEXT NOT NULL,
                type TEXT NOT NULL CHECK (type IN ('income', 'expense')),
                category_id INTEGER NOT NULL,
                amount REAL NOT NULL CHECK (amount > 0),
                currency TEXT NOT NULL DEFAULT 'USD' CHECK (currency IN ('USD', 'KES')),
                description TEXT,
                FOREIGN KEY (user_id) REFERENCES users (id),
                FOREIGN KEY (category_id) REFERENCES categories (id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS budgets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                category_id INTEGER NOT NULL,
                month TEXT NOT NULL,
                limit_amount REAL NOT NULL CHECK (limit_amount > 0),
                UNIQUE(user_id, category_id, month),
                FOREIGN KEY (user_id) REFERENCES users (id),
                FOREIGN KEY (category_id) REFERENCES categories (id)
            )
            """
        )

        for table in ("categories", "transactions", "budgets"):
            columns = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
            if "user_id" not in columns:
                conn.execute(
                    f"ALTER TABLE {table} ADD COLUMN user_id INTEGER REFERENCES users(id)"
                )

        transaction_columns = {
            row[1] for row in conn.execute("PRAGMA table_info(transactions)")
        }
        if "currency" not in transaction_columns:
            conn.execute(
                "ALTER TABLE transactions ADD COLUMN currency TEXT NOT NULL DEFAULT 'USD'"
            )

        first_user = conn.execute("SELECT id FROM users ORDER BY id LIMIT 1").fetchone()
        if first_user:
            conn.execute(
                "UPDATE categories SET user_id = ? WHERE user_id IS NULL",
                (first_user["id"],),
            )
            conn.execute(
                "UPDATE transactions SET user_id = ? WHERE user_id IS NULL",
                (first_user["id"],),
            )
            conn.execute(
                "UPDATE budgets SET user_id = ? WHERE user_id IS NULL",
                (first_user["id"],),
            )

        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS categories_user_name "
            "ON categories(user_id, name)"
        )
        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS budgets_user_category_month "
            "ON budgets(user_id, category_id, month)"
        )


# ---------------------------------------------------------------------------
# Users / auth
# ---------------------------------------------------------------------------

def create_user(username: str, password: str) -> int:
    """Creates a user, seeds their default categories, and returns the new user_id."""
    username = username.strip()
    password_hash = auth.hash_password(password)
    with get_connection() as conn:
        existing = conn.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
        if existing:
            raise ValueError("That username is already taken.")
        cursor = conn.execute(
            "INSERT INTO users (username, password_hash) VALUES (?, ?)", (username, password_hash)
        )
        user_id = cursor.lastrowid
        conn.executemany(
            "INSERT OR IGNORE INTO categories (user_id, name, type) VALUES (?, ?, ?)",
            [(user_id, name, type_) for name, type_ in DEFAULT_CATEGORIES],
        )
        conn.execute(
            "UPDATE categories SET user_id = ? WHERE user_id IS NULL", (user_id,)
        )
        conn.execute(
            "UPDATE transactions SET user_id = ? WHERE user_id IS NULL", (user_id,)
        )
        conn.execute(
            "UPDATE budgets SET user_id = ? WHERE user_id IS NULL", (user_id,)
        )
        return user_id


def authenticate_user(username: str, password: str):
    """Returns the user dict if credentials are valid, else None."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE username = ?", (username.strip(),)
        ).fetchone()
        if row and auth.verify_password(password, row["password_hash"]):
            return dict(row)
        return None


def get_user_by_id(user_id: int):
    with get_connection() as conn:
        row = conn.execute("SELECT id, username, created_at FROM users WHERE id = ?", (user_id,)).fetchone()
        return dict(row) if row else None


# ---------------------------------------------------------------------------
# Categories
# ---------------------------------------------------------------------------

def add_category(user_id: int, name: str, type_: str):
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO categories (user_id, name, type) VALUES (?, ?, ?)",
            (user_id, name.strip(), type_),
        )


def get_categories(user_id: int, type_: str = None):
    with get_connection() as conn:
        if type_:
            rows = conn.execute(
                "SELECT * FROM categories WHERE user_id = ? AND type = ? ORDER BY name",
                (user_id, type_),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM categories WHERE user_id = ? ORDER BY type, name", (user_id,)
            ).fetchall()
        return [dict(r) for r in rows]


def delete_category(user_id: int, category_id: int):
    with get_connection() as conn:
        in_use = conn.execute(
            "SELECT COUNT(*) AS c FROM transactions WHERE category_id = ? AND user_id = ?",
            (category_id, user_id),
        ).fetchone()["c"]
        if in_use > 0:
            raise ValueError("Cannot delete a category that has transactions.")
        conn.execute(
            "DELETE FROM categories WHERE id = ? AND user_id = ?", (category_id, user_id)
        )


# ---------------------------------------------------------------------------
# Transactions
# ---------------------------------------------------------------------------

def add_transaction(
    user_id: int,
    date_: str,
    type_: str,
    category_id: int,
    amount: float,
    description: str = "",
    currency: str = "USD",
):
    if amount <= 0:
        raise ValueError("Amount must be greater than zero.")
    if type_ not in ("income", "expense"):
        raise ValueError("Type must be 'income' or 'expense'.")
    if currency not in ("USD", "KES"):
        raise ValueError("Currency must be 'USD' or 'KES'.")
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO transactions (user_id, date, type, category_id, amount, currency, description)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (user_id, date_, type_, category_id, amount, currency, description.strip()),
        )


def update_transaction(
    user_id: int,
    txn_id: int,
    date_: str,
    type_: str,
    category_id: int,
    amount: float,
    description: str = "",
    currency: str = "USD",
):
    if amount <= 0:
        raise ValueError("Amount must be greater than zero.")
    if currency not in ("USD", "KES"):
        raise ValueError("Currency must be 'USD' or 'KES'.")
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE transactions
            SET date = ?, type = ?, category_id = ?, amount = ?, currency = ?, description = ?
            WHERE id = ? AND user_id = ?
            """,
            (date_, type_, category_id, amount, currency, description.strip(), txn_id, user_id),
        )


def delete_transaction(user_id: int, txn_id: int):
    with get_connection() as conn:
        conn.execute("DELETE FROM transactions WHERE id = ? AND user_id = ?", (txn_id, user_id))


def get_transactions(user_id: int, start_date: str = None, end_date: str = None, type_: str = None, category_id: int = None):
    query = """
        SELECT t.id, t.date, t.type, t.amount, t.currency, t.description,
               c.name AS category, c.id AS category_id
        FROM transactions t
        JOIN categories c ON t.category_id = c.id
        WHERE t.user_id = ?
    """
    params = [user_id]
    if start_date:
        query += " AND t.date >= ?"
        params.append(start_date)
    if end_date:
        query += " AND t.date <= ?"
        params.append(end_date)
    if type_:
        query += " AND t.type = ?"
        params.append(type_)
    if category_id:
        query += " AND t.category_id = ?"
        params.append(category_id)
    query += " ORDER BY t.date DESC, t.id DESC"

    with get_connection() as conn:
        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Budgets
# ---------------------------------------------------------------------------

def set_budget(user_id: int, category_id: int, month: str, limit_amount: float):
    """month format: 'YYYY-MM'. Upserts the budget for that user/category/month."""
    if limit_amount <= 0:
        raise ValueError("Budget limit must be greater than zero.")
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO budgets (user_id, category_id, month, limit_amount)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id, category_id, month) DO UPDATE SET limit_amount = excluded.limit_amount
            """,
            (user_id, category_id, month, limit_amount),
        )


def get_budgets(user_id: int, month: str = None):
    query = """
        SELECT b.id, b.category_id, c.name AS category, b.month, b.limit_amount
        FROM budgets b
        JOIN categories c ON b.category_id = c.id
        WHERE b.user_id = ?
    """
    params = [user_id]
    if month:
        query += " AND b.month = ?"
        params.append(month)
    query += " ORDER BY c.name"
    with get_connection() as conn:
        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]


def delete_budget(user_id: int, budget_id: int):
    with get_connection() as conn:
        conn.execute("DELETE FROM budgets WHERE id = ? AND user_id = ?", (budget_id, user_id))
