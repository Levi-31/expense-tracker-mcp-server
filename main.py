from fastmcp import FastMCP
import os
import sqlite3

DB_PATH = os.path.join(os.path.dirname(__file__), "expenses.db")
CATEGORIES_PATH = os.path.join(os.path.dirname(__file__), "categories.json")

mcp = FastMCP("ExpenseTracker")


def init_db():
    with sqlite3.connect(DB_PATH) as c:

        c.execute("""
        CREATE TABLE IF NOT EXISTS expenses(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            amount REAL NOT NULL,
            category TEXT NOT NULL,
            subcategory TEXT DEFAULT '',
            note TEXT DEFAULT ''
        )
        """)

        c.execute("""
        CREATE TABLE IF NOT EXISTS monthly_finance(
            month TEXT PRIMARY KEY,
            budget REAL NOT NULL DEFAULT 0,
            credit REAL NOT NULL DEFAULT 0
        )
        """)


init_db()


# -------------------------------------------------------
# Expenses
# -------------------------------------------------------

@mcp.tool()
def add_expense(
    date,
    amount,
    category,
    subcategory="",
    note=""
):
    """
    Add a new expense.
    Date format: YYYY-MM-DD
    """

    with sqlite3.connect(DB_PATH) as c:
        cur = c.execute(
            """
            INSERT INTO expenses
            (date, amount, category, subcategory, note)
            VALUES (?,?,?,?,?)
            """,
            (
                date,
                amount,
                category,
                subcategory,
                note
            )
        )

        return {
            "status": "ok",
            "expense_id": cur.lastrowid
        }


@mcp.tool()
def list_expenses(start_date, end_date):
    """
    List all expenses between two dates.
    """

    with sqlite3.connect(DB_PATH) as c:

        cur = c.execute(
            """
            SELECT
                id,
                date,
                amount,
                category,
                subcategory,
                note
            FROM expenses
            WHERE date BETWEEN ? AND ?
            ORDER BY date,id
            """,
            (start_date, end_date)
        )

        cols = [x[0] for x in cur.description]

        return [
            dict(zip(cols, row))
            for row in cur.fetchall()
        ]


# -------------------------------------------------------
# Monthly Finance
# -------------------------------------------------------

@mcp.tool()
def set_monthly_budget(month, budget):
    """
    Set monthly budget.

    month format:
    YYYY-MM
    """

    with sqlite3.connect(DB_PATH) as c:

        c.execute("""
        INSERT INTO monthly_finance(month,budget)
        VALUES(?,?)
        ON CONFLICT(month)
        DO UPDATE SET budget=excluded.budget
        """, (month, budget))

        return {
            "status": "ok",
            "month": month,
            "budget": budget
        }


@mcp.tool()
def set_monthly_credit(month, credit):
    """
    Set monthly available credit/income.

    month format:
    YYYY-MM
    """

    with sqlite3.connect(DB_PATH) as c:

        c.execute("""
        INSERT INTO monthly_finance(month,credit)
        VALUES(?,?)
        ON CONFLICT(month)
        DO UPDATE SET credit=excluded.credit
        """, (month, credit))

        return {
            "status": "ok",
            "month": month,
            "credit": credit
        }


@mcp.tool()
def get_monthly_finance(month):
    """
    Get configured budget and credit for a month.
    """

    with sqlite3.connect(DB_PATH) as c:

        cur = c.execute("""
        SELECT
            budget,
            credit
        FROM monthly_finance
        WHERE month=?
        """, (month,))

        row = cur.fetchone()

        if row is None:
            return {
                "month": month,
                "budget": 0,
                "credit": 0
            }

        return {
            "month": month,
            "budget": row[0],
            "credit": row[1]
        }


# -------------------------------------------------------
# Summary
# -------------------------------------------------------

@mcp.tool()
def summarize(start_date, end_date, category=None):
    """
    Expense summary.

    Returns

    - category wise totals
    - total expenses
    - budget
    - remaining budget
    - remaining credit
    - over budget amount
    """

    month = start_date[:7]

    with sqlite3.connect(DB_PATH) as c:

        query = """
        SELECT
            category,
            SUM(amount)
        FROM expenses
        WHERE date BETWEEN ? AND ?
        """

        params = [start_date, end_date]

        if category:
            query += " AND category=?"
            params.append(category)

        query += """
        GROUP BY category
        ORDER BY category
        """

        cur = c.execute(query, params)

        category_summary = [
            {
                "category": row[0],
                "total_amount": row[1]
            }
            for row in cur.fetchall()
        ]

        cur = c.execute("""
        SELECT COALESCE(SUM(amount),0)
        FROM expenses
        WHERE date BETWEEN ? AND ?
        """, (start_date, end_date))

        total_expense = cur.fetchone()[0]

        cur = c.execute("""
        SELECT
            budget,
            credit
        FROM monthly_finance
        WHERE month=?
        """, (month,))

        row = cur.fetchone()

        budget = row[0] if row else 0
        credit = row[1] if row else 0

        remaining_budget = budget - total_expense
        remaining_credit = credit - total_expense

        over_budget = max(0, total_expense - budget)

        budget_utilization = (
            round((total_expense / budget) * 100, 2)
            if budget > 0
            else None
        )

        return {

            "month": month,

            "category_summary": category_summary,

            "total_expense": total_expense,

            "budget": budget,

            "credit": credit,

            "remaining_budget": remaining_budget,

            "remaining_credit": remaining_credit,

            "budget_utilization_percent": budget_utilization,

            "is_over_budget": total_expense > budget if budget > 0 else False,

            "over_budget_amount": over_budget,

            "budget_status": (
                f"Over budget by ₹{over_budget:.2f}"
                if budget > 0 and total_expense > budget
                else (
                    f"₹{remaining_budget:.2f} budget remaining"
                    if budget > 0
                    else "Budget not configured"
                )
            ),

            "credit_status": (
                f"₹{remaining_credit:.2f} credit remaining"
                if credit > 0
                else "Credit not configured"
            )

        }


# -------------------------------------------------------
# Resources
# -------------------------------------------------------

@mcp.resource(
    "expense://categories",
    mime_type="application/json"
)
def categories():
    with open(
        CATEGORIES_PATH,
        "r",
        encoding="utf-8"
    ) as f:
        return f.read()


if __name__ == "__main__":
    mcp.run(transport="http",host='0.0.0.0',port=8000)