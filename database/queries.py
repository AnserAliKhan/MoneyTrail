# Database query helpers for Spendly.
#
# Provides reusable query functions for CRUD operations on expenses.
# All functions use raw sqlite3 via get_db() with parameterized queries.

import sqlite3

from database.db import get_db


def get_expense_by_id(expense_id: int, user_id: int) -> sqlite3.Row | None:
    """Fetch a single expense scoped to the given user.

    Args:
        expense_id: The ID of the expense to fetch
        user_id: The ID of the user who owns the expense

    Returns:
        The expense row if found and owned by the user, None otherwise.
    """
    db = get_db()
    row = db.execute(
        "SELECT id, user_id, amount, category, date, description FROM expenses WHERE id = ? AND user_id = ?",
        (expense_id, user_id),
    ).fetchone()
    return row


def update_expense(expense_id: int, user_id: int, amount: float, category: str, date: str, description: str | None) -> bool:
    """Update an expense, scoped to user_id for security.

    Args:
        expense_id: The ID of the expense to update
        user_id: The ID of the user who owns the expense
        amount: The new expense amount (positive number)
        category: The new category name (must be from CATEGORIES)
        date: The new expense date in YYYY-MM-DD format
        description: Optional description, can be None or empty string

    Returns:
        True if the expense was updated, False if no rows affected.
    """
    db = get_db()
    cursor = db.execute(
        """
        UPDATE expenses
        SET amount = ?, category = ?, date = ?, description = ?
        WHERE id = ? AND user_id = ?
        """,
        (amount, category, date, description if description else None, expense_id, user_id),
    )
    db.commit()
    return cursor.rowcount > 0


def delete_expense(expense_id: int, user_id: int) -> bool:
    """Delete an expense, scoped to user_id for security.

    Args:
        expense_id: The ID of the expense to delete
        user_id: The ID of the user who owns the expense

    Returns:
        True if the expense was deleted, False if no rows affected.
    """
    db = get_db()
    cursor = db.execute(
        "DELETE FROM expenses WHERE id = ? AND user_id = ?",
        (expense_id, user_id),
    )
    db.commit()
    return cursor.rowcount > 0


def insert_expense(user_id: int, amount: float, category: str, date: str, description: str | None) -> int:
    """Insert a new expense and return its ID.

    Args:
        user_id: The ID of the user creating the expense
        amount: The expense amount (positive number)
        category: The category name (must be from CATEGORIES)
        date: The expense date in YYYY-MM-DD format
        description: Optional description, can be None or empty string

    Returns:
        The rowid of the newly inserted expense
    """
    db = get_db()
    cursor = db.execute(
        """
        INSERT INTO expenses (user_id, amount, category, date, description)
        VALUES (?, ?, ?, ?, ?)
        """,
        (user_id, amount, category, date, description if description else None),
    )
    db.commit()
    return cursor.lastrowid
