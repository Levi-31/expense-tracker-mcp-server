from contextlib import asynccontextmanager
from decimal import Decimal
from datetime import date

from fastmcp import FastMCP, Context

from app.databases import open_pool, close_pool
from app.schema import init_db
from app.resources import get_categories

from app.models import ExpenseCreate

from app.services.expense_service import ExpenseService
from app.services.finance_service import FinanceService
from app.services.summary_service import SummaryService
from app.repository.user_repository import UserRepository


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
        "You must first ask the user to log in if they haven't done so in this session. "
        "Use the login(email) tool to authenticate the user and save their session. "
        "Once logged in, you do not need to provide the 'email' parameter for subsequent tool calls. "
        "If you get an 'unauthenticated' status code, prompt the user to log in."
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
# Authentication Tools
# ---------------------------------------------------------

@mcp.tool()
async def login(
    email: str,
    ctx: Context,
) -> dict:
    """
    Log in a user by their email. Automatically creates the user if they don't exist.
    Stores the user session state in the active MCP connection.
    """
    normalized_email = email.strip().lower()
    await UserRepository.get_or_create_user(normalized_email)
    await ctx.set_state("email", normalized_email)
    return {
        "status": "ok",
        "message": f"Successfully logged in as {normalized_email}",
        "email": normalized_email,
    }


@mcp.tool()
async def logout(
    ctx: Context,
) -> dict:
    """
    Logs out the current user session and clears the session state.
    """
    await ctx.delete_state("email")
    return {
        "status": "ok",
        "message": "Successfully logged out.",
    }


@mcp.tool()
async def get_current_user(
    ctx: Context,
) -> dict:
    """
    Returns the currently logged-in user email in this session.
    """
    email = await ctx.get_state("email")
    if not email:
        return {
            "status": "unauthenticated",
            "message": "No active session. Please login first.",
        }
    return {
        "status": "ok",
        "email": email,
    }


# ---------------------------------------------------------
# Expense Tools
# ---------------------------------------------------------

@mcp.tool()
async def add_expense(
    ctx: Context,
    date: str,
    amount: float,
    category: str,
    subcategory: str = "",
    note: str = "",
    is_borrowed: bool = False,
    is_settled: bool = False,
    email: str | None = None,
):
    """
    Add a new expense. Resolves the user from session or takes optional email.
    """
    active_email = email or await ctx.get_state("email")
    if not active_email:
        return {
            "status": "unauthenticated",
            "message": "No active session. Please login first using login(email='user@example.com').",
        }

    expense = ExpenseCreate(
        date=date,
        amount=Decimal(str(amount)),
        category=category,
        subcategory=subcategory,
        note=note,
        is_borrowed=is_borrowed,
        is_settled=is_settled,
    )

    return await ExpenseService.add_expense(
        active_email,
        expense,
    )


@mcp.tool()
async def list_expenses(
    ctx: Context,
    start_date: date,
    end_date: date,
    email: str | None = None,
):
    """
    List expenses within a date range. Resolves user from session or takes optional email.
    """
    active_email = email or await ctx.get_state("email")
    if not active_email:
        return {
            "status": "unauthenticated",
            "message": "No active session. Please login first using login(email='user@example.com').",
        }

    return await ExpenseService.list_expenses(
        active_email,
        start_date,
        end_date,
    )


@mcp.tool()
async def update_expense(
    ctx: Context,
    expense_id: int,
    date: str,
    amount: float,
    category: str,
    subcategory: str = "",
    note: str = "",
    is_borrowed: bool = False,
    is_settled: bool = False,
    email: str | None = None,
):
    """
    Update an existing expense. Resolves user from session or takes optional email.
    """
    active_email = email or await ctx.get_state("email")
    if not active_email:
        return {
            "status": "unauthenticated",
            "message": "No active session. Please login first using login(email='user@example.com').",
        }

    expense = ExpenseCreate(
        date=date,
        amount=Decimal(str(amount)),
        category=category,
        subcategory=subcategory,
        note=note,
        is_borrowed=is_borrowed,
        is_settled=is_settled,
    )

    return await ExpenseService.update_expense(
        active_email,
        expense_id,
        expense,
    )


@mcp.tool()
async def delete_expense(
    ctx: Context,
    expense_id: int,
    email: str | None = None,
):
    """
    Delete an expense. Resolves user from session or takes optional email.
    """
    active_email = email or await ctx.get_state("email")
    if not active_email:
        return {
            "status": "unauthenticated",
            "message": "No active session. Please login first using login(email='user@example.com').",
        }

    return await ExpenseService.delete_expense(
        active_email,
        expense_id,
    )


@mcp.tool()
async def recent_expenses(
    ctx: Context,
    limit: int = 10,
    email: str | None = None,
):
    """
    Return latest expenses. Resolves user from session or takes optional email.
    """
    active_email = email or await ctx.get_state("email")
    if not active_email:
        return {
            "status": "unauthenticated",
            "message": "No active session. Please login first using login(email='user@example.com').",
        }

    return await ExpenseService.recent(
        active_email,
        limit,
    )


@mcp.tool()
async def settle_borrowed_expense(
    ctx: Context,
    expense_id: int,
    is_settled: bool = True,
    email: str | None = None,
) -> dict:
    """
    Mark an outstanding borrowed expense as settled (repaid). Resolves user from session or takes optional email.
    """
    active_email = email or await ctx.get_state("email")
    if not active_email:
        return {
            "status": "unauthenticated",
            "message": "No active session. Please login first using login(email='user@example.com').",
        }

    return await ExpenseService.settle_expense(
        active_email,
        expense_id,
        is_settled,
    )


# ---------------------------------------------------------
# Finance Tools
# ---------------------------------------------------------

@mcp.tool()
async def set_monthly_budget(
    ctx: Context,
    month: str,
    budget: float,
    email: str | None = None,
):
    """
    Set monthly budget. Resolves user from session or takes optional email.
    """
    active_email = email or await ctx.get_state("email")
    if not active_email:
        return {
            "status": "unauthenticated",
            "message": "No active session. Please login first using login(email='user@example.com').",
        }

    return await FinanceService.set_budget(
        active_email,
        month,
        Decimal(str(budget)),
    )


@mcp.tool()
async def set_monthly_credit(
    ctx: Context,
    month: str,
    credit: float,
    email: str | None = None,
):
    """
    Set monthly credit. Resolves user from session or takes optional email.
    """
    active_email = email or await ctx.get_state("email")
    if not active_email:
        return {
            "status": "unauthenticated",
            "message": "No active session. Please login first using login(email='user@example.com').",
        }

    return await FinanceService.set_credit(
        active_email,
        month,
        Decimal(str(credit)),
    )


@mcp.tool()
async def get_monthly_finance(
    ctx: Context,
    month: str,
    email: str | None = None,
):
    """
    Get configured budget & credit. Resolves user from session or takes optional email.
    """
    active_email = email or await ctx.get_state("email")
    if not active_email:
        return {
            "status": "unauthenticated",
            "message": "No active session. Please login first using login(email='user@example.com').",
        }

    return await FinanceService.get_month(
        active_email,
        month,
    )


# ---------------------------------------------------------
# Summary
# ---------------------------------------------------------

@mcp.tool()
async def summarize(
    ctx: Context,
    start_date: date,
    end_date: date,
    category: str | None = None,
    email: str | None = None,
):
    """
    Dashboard summary. Resolves user from session or takes optional email.
    """
    active_email = email or await ctx.get_state("email")
    if not active_email:
        return {
            "status": "unauthenticated",
            "message": "No active session. Please login first using login(email='user@example.com').",
        }

    return await SummaryService.summarize(
        active_email,
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