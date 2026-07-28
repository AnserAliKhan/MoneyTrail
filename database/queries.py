# Database query helpers for Spendly.
#
# Provides reusable query functions for CRUD operations on expenses.
# All functions use raw sqlite3 via get_db() with parameterized queries.

from database.db import get_db


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
