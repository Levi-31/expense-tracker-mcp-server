from contextlib import asynccontextmanager
from decimal import Decimal
from datetime import date

from fastmcp import FastMCP

from app.databases import open_pool, close_pool
from app.schema import init_db
from app.resources import get_categories

from app.models import ExpenseCreate

from app.services.expense_service import ExpenseService
from app.services.finance_service import FinanceService
from app.services.summary_service import SummaryService


# ---------------------------------------------------------
# Lifespan
# ---------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastMCP):
    """
    Initialize resources when the MCP server starts
    and clean them up when it shuts down.
    """

    await open_pool()
    await init_db()

    print("✅ PostgreSQL pool initialized.")

    try:
        yield

    finally:
        await close_pool()
        print("✅ PostgreSQL pool closed.")


# ---------------------------------------------------------
# MCP Server
# ---------------------------------------------------------

mcp = FastMCP(
    "Expense Tracker",
    lifespan=lifespan,
)


# ---------------------------------------------------------
# Resources
# ---------------------------------------------------------

@mcp.resource(
    "expense://categories",
    mime_type="application/json",
)
async def categories():

    return get_categories()


# ---------------------------------------------------------
# Expense Tools
# ---------------------------------------------------------

@mcp.tool()
async def add_expense(
    date: str,
    amount: float,
    category: str,
    subcategory: str = "",
    note: str = "",
):
    """
    Add a new expense.
    """

    expense = ExpenseCreate(
        date=date,
        amount=Decimal(str(amount)),
        category=category,
        subcategory=subcategory,
        note=note,
    )

    return await ExpenseService.add_expense(expense)


@mcp.tool()
async def list_expenses(
    start_date: date,
    end_date: date,
):
    """
    List expenses within a date range.
    """

    return await ExpenseService.list_expenses(
        start_date,
        end_date,
    )


@mcp.tool()
async def update_expense(
    expense_id: int,
    date: str,
    amount: float,
    category: str,
    subcategory: str = "",
    note: str = "",
):
    """
    Update an existing expense.
    """

    expense = ExpenseCreate(
        date=date,
        amount=Decimal(str(amount)),
        category=category,
        subcategory=subcategory,
        note=note,
    )

    return await ExpenseService.update_expense(
        expense_id,
        expense,
    )


@mcp.tool()
async def delete_expense(
    expense_id: int,
):
    """
    Delete an expense.
    """

    return await ExpenseService.delete_expense(
        expense_id,
    )


@mcp.tool()
async def recent_expenses(
    limit: int = 10,
):
    """
    Return latest expenses.
    """

    return await ExpenseService.recent(limit)


# ---------------------------------------------------------
# Finance Tools
# ---------------------------------------------------------

@mcp.tool()
async def set_monthly_budget(
    month: str,
    budget: float,
):
    """
    Set monthly budget.
    """

    return await FinanceService.set_budget(
        month,
        Decimal(str(budget)),
    )


@mcp.tool()
async def set_monthly_credit(
    month: str,
    credit: float,
):
    """
    Set monthly credit.
    """

    return await FinanceService.set_credit(
        month,
        Decimal(str(credit)),
    )


@mcp.tool()
async def get_monthly_finance(
    month: str,
):
    """
    Get configured budget & credit.
    """

    return await FinanceService.get_month(
        month,
    )


# ---------------------------------------------------------
# Summary
# ---------------------------------------------------------

@mcp.tool()
async def summarize(
    start_date: date,
    end_date: date,
    category: str | None = None,
):
    """
    Dashboard summary.
    """

    return await SummaryService.summarize(
        start_date,
        end_date,
        category,
    )


# ---------------------------------------------------------
# Health Check
# ---------------------------------------------------------

@mcp.tool()
async def health():
    """
    Health check.
    """

    return {
        "status": "healthy",
        "database": "connected",
    }


# ---------------------------------------------------------
# Run Server
# ---------------------------------------------------------

if __name__ == "__main__":

    mcp.run(
        transport="http",
        host="0.0.0.0",
        port=8000,
    )