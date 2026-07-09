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
    instructions=(
        "Every tool requires a 'username' parameter. "
        "Before calling any tool, you MUST identify the user. "
        "Extract the username from the user's email "
        "(the part before the @), or from their name if provided. "
        "If you cannot determine the username, "
        "ask the user before proceeding. "
        "Never guess or fabricate a username."
    ),
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
    username: str,
    date: str,
    amount: float,
    category: str,
    subcategory: str = "",
    note: str = "",
):
    """
    Add a new expense for a user.
    """

    expense = ExpenseCreate(
        date=date,
        amount=Decimal(str(amount)),
        category=category,
        subcategory=subcategory,
        note=note,
    )

    return await ExpenseService.add_expense(
        username,
        expense,
    )


@mcp.tool()
async def list_expenses(
    username: str,
    start_date: date,
    end_date: date,
):
    """
    List expenses within a date range for a user.
    """

    return await ExpenseService.list_expenses(
        username,
        start_date,
        end_date,
    )


@mcp.tool()
async def update_expense(
    username: str,
    expense_id: int,
    date: str,
    amount: float,
    category: str,
    subcategory: str = "",
    note: str = "",
):
    """
    Update an existing expense for a user.
    """

    expense = ExpenseCreate(
        date=date,
        amount=Decimal(str(amount)),
        category=category,
        subcategory=subcategory,
        note=note,
    )

    return await ExpenseService.update_expense(
        username,
        expense_id,
        expense,
    )


@mcp.tool()
async def delete_expense(
    username: str,
    expense_id: int,
):
    """
    Delete an expense for a user.
    """

    return await ExpenseService.delete_expense(
        username,
        expense_id,
    )


@mcp.tool()
async def recent_expenses(
    username: str,
    limit: int = 10,
):
    """
    Return latest expenses for a user.
    """

    return await ExpenseService.recent(
        username,
        limit,
    )


# ---------------------------------------------------------
# Finance Tools
# ---------------------------------------------------------

@mcp.tool()
async def set_monthly_budget(
    username: str,
    month: str,
    budget: float,
):
    """
    Set monthly budget for a user.
    """

    return await FinanceService.set_budget(
        username,
        month,
        Decimal(str(budget)),
    )


@mcp.tool()
async def set_monthly_credit(
    username: str,
    month: str,
    credit: float,
):
    """
    Set monthly credit for a user.
    """

    return await FinanceService.set_credit(
        username,
        month,
        Decimal(str(credit)),
    )


@mcp.tool()
async def get_monthly_finance(
    username: str,
    month: str,
):
    """
    Get configured budget & credit for a user.
    """

    return await FinanceService.get_month(
        username,
        month,
    )


# ---------------------------------------------------------
# Summary
# ---------------------------------------------------------

@mcp.tool()
async def summarize(
    username: str,
    start_date: date,
    end_date: date,
    category: str | None = None,
):
    """
    Dashboard summary for a user.
    """

    return await SummaryService.summarize(
        username,
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