from contextlib import asynccontextmanager
from decimal import Decimal
from datetime import date
import os
import httpx

from fastmcp import FastMCP, Context
from starlette.requests import Request
from starlette.responses import HTMLResponse, RedirectResponse, Response

from app.databases import open_pool, close_pool
from app.schema import init_db
from app.resources import get_categories

from app.models import ExpenseCreate

from app.services.expense_service import ExpenseService
from app.services.finance_service import FinanceService
from app.services.summary_service import SummaryService
from app.repository.user_repository import UserRepository
from app.repository.session_repository import SessionRepository
from contextvars import ContextVar
import uuid
from starlette.datastructures import QueryParams
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware

current_scope: ContextVar = ContextVar("current_scope", default=None)

class ScopeMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        current_scope.set(scope)
        await self.app(scope, receive, send)


def custom_uuid4() -> uuid.UUID:
    scope = current_scope.get()
    if scope and scope.get("type") == "http":
        # Check for client_id query parameter (uniform way to persist sessions for all LLMs)
        query_string = scope.get("query_string", b"").decode("utf-8")
        params = QueryParams(query_string)
        client_id = params.get("client_id")
        if client_id:
            # Generate a deterministic UUID based on client_id
            return uuid.uuid5(uuid.NAMESPACE_DNS, client_id)
    return uuid.uuid4()

import mcp.server.sse
mcp.server.sse.uuid4 = custom_uuid4


def get_session_id(ctx: Context) -> str:
    request_ctx = getattr(ctx, "request_context", None)
    if request_ctx is not None:
        request = getattr(request_ctx, "request", None)
        if request is not None:
            # 1. Check for client_id query parameter — derive a deterministic session ID
            #    This works across ALL transports (SSE and Streamable HTTP) and survives
            #    Cloud Run cold starts because it's derived from the URL, not in-memory state.
            client_id = request.query_params.get("client_id")
            if client_id:
                return str(uuid.uuid5(uuid.NAMESPACE_DNS, client_id))
            # 2. Check SSE query parameter session_id
            session_id = request.query_params.get("session_id")
            if session_id:
                return session_id
            # 3. Check header
            session_id = request.headers.get("mcp-session-id")
            if session_id:
                return session_id
    return ctx.session_id


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
        "Use the google_login() tool to authenticate the user. It will return a Google Sign-In link. "
        "Ask the user to open this link in their browser. Once they complete the sign-in, ask them to verify and then proceed. "
        "Under the hood, their session will be automatically authenticated after they sign in. "
        "If you get an 'unauthenticated' status code, prompt the user to log in via google_login().\n\n"
        "CRITICAL RULE: Whenever a credit card expense is being added (or using the 'credit_card_usage' category), "
        "if the user has not specified whether it is for self-use or borrowed by a friend, you MUST ask the user "
        "for clarification (e.g. 'Is this credit card expense for self-use or was it borrowed by a friend?') "
        "before invoking the add_expense tool."
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
async def google_login(
    ctx: Context,
    base_url: str | None = None,
) -> dict:
    """
    Returns the Google Sign-In authentication URL for this session.
    Instruct the user to visit this URL to log in.

    Args:
        base_url: Optional host URL override (e.g. 'https://your-app.a.run.app').
                  Defaults to the server's configured PUBLIC_URL or localhost.
    """
    from app.config import GOOGLE_CLIENT_ID
    if not GOOGLE_CLIENT_ID:
        return {
            "status": "error",
            "message": "Google OAuth is not configured on this server (missing GOOGLE_CLIENT_ID).",
        }

    host_url = base_url or os.getenv("PUBLIC_URL")
    if not host_url:
        request_ctx = getattr(ctx, "request_context", None)
        if request_ctx is not None:
            request = getattr(request_ctx, "request", None)
            if request is not None:
                host_url = f"{request.url.scheme}://{request.headers.get('host')}"
    if not host_url:
        host_url = "http://localhost:8000"

    auth_url = f"{host_url.rstrip('/')}/auth/google?session_id={get_session_id(ctx)}"

    return {
        "status": "needs_authentication",
        "auth_url": auth_url,
        "message": (
            "To sign in with Google, please open this link in your browser:\n\n"
            f"{auth_url}\n\n"
            "Once you complete the sign-in, ask me to check if you are logged in."
        ),
    }


@mcp.tool()
async def logout(
    ctx: Context,
) -> dict:
    """
    Logs out the current user session and clears the session state.
    """
    await SessionRepository.delete_session(get_session_id(ctx))
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
    session = await SessionRepository.get_session(get_session_id(ctx))
    if not session:
        return {
            "status": "unauthenticated",
            "message": "No active session. Please log in first using the google_login tool.",
        }
    return {
        "status": "ok",
        "email": session["email"],
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
):
    """
    Add a new expense.

    Args:
        date: Date of the expense formatted as YYYY-MM-DD.
        amount: Positive numeric amount.
        category: Category name.
        subcategory: Subcategory name.
        note: Description of the expense.
        is_borrowed: Set to True if this expense was borrowed by a friend. CRITICAL: If a credit card expense is added and the user has not specified whether it is for self-use or borrowed by a friend, you MUST ask the user in chat for clarification before calling this tool.
        is_settled: Set to True if the borrowed expense was repaid.
    """
    session = await SessionRepository.get_session(get_session_id(ctx))
    if not session:
        return {
            "status": "unauthenticated",
            "message": "No active session. Please log in first using the google_login tool.",
        }
    active_email = session["email"]

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
):
    """
    List expenses within a date range.
    """
    session = await SessionRepository.get_session(get_session_id(ctx))
    if not session:
        return {
            "status": "unauthenticated",
            "message": "No active session. Please log in first using the google_login tool.",
        }
    active_email = session["email"]

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
):
    """
    Update an existing expense.

    Args:
        expense_id: The ID of the expense to update.
        date: Date of the expense formatted as YYYY-MM-DD.
        amount: Positive numeric amount.
        category: Category name.
        subcategory: Subcategory name.
        note: Description of the expense.
        is_borrowed: Set to True if this expense was borrowed by a friend. CRITICAL: If a credit card expense is updated and the user has not specified whether it is for self-use or borrowed by a friend, you MUST ask the user in chat for clarification before calling this tool.
        is_settled: Set to True if the borrowed expense was repaid.
    """
    session = await SessionRepository.get_session(get_session_id(ctx))
    if not session:
        return {
            "status": "unauthenticated",
            "message": "No active session. Please log in first using the google_login tool.",
        }
    active_email = session["email"]

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
):
    """
    Delete an expense.
    """
    session = await SessionRepository.get_session(get_session_id(ctx))
    if not session:
        return {
            "status": "unauthenticated",
            "message": "No active session. Please log in first using the google_login tool.",
        }
    active_email = session["email"]

    return await ExpenseService.delete_expense(
        active_email,
        expense_id,
    )


@mcp.tool()
async def recent_expenses(
    ctx: Context,
    limit: int = 10,
):
    """
    Return latest expenses.
    """
    session = await SessionRepository.get_session(get_session_id(ctx))
    if not session:
        return {
            "status": "unauthenticated",
            "message": "No active session. Please log in first using the google_login tool.",
        }
    active_email = session["email"]

    return await ExpenseService.recent(
        active_email,
        limit,
    )


@mcp.tool()
async def settle_borrowed_expense(
    ctx: Context,
    expense_id: int,
    is_settled: bool = True,
) -> dict:
    """
    Mark an outstanding borrowed expense as settled (repaid).
    """
    session = await SessionRepository.get_session(get_session_id(ctx))
    if not session:
        return {
            "status": "unauthenticated",
            "message": "No active session. Please log in first using the google_login tool.",
        }
    active_email = session["email"]

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
):
    """
    Set monthly budget.
    """
    session = await SessionRepository.get_session(get_session_id(ctx))
    if not session:
        return {
            "status": "unauthenticated",
            "message": "No active session. Please log in first using the google_login tool.",
        }
    active_email = session["email"]

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
):
    """
    Set monthly income (salary / net income).
    """
    session = await SessionRepository.get_session(get_session_id(ctx))
    if not session:
        return {
            "status": "unauthenticated",
            "message": "No active session. Please log in first using the google_login tool.",
        }
    active_email = session["email"]

    return await FinanceService.set_credit(
        active_email,
        month,
        Decimal(str(credit)),
    )


@mcp.tool()
async def get_monthly_finance(
    ctx: Context,
    month: str,
):
    """
    Get configured budget & income.
    """
    session = await SessionRepository.get_session(get_session_id(ctx))
    if not session:
        return {
            "status": "unauthenticated",
            "message": "No active session. Please log in first using the google_login tool.",
        }
    active_email = session["email"]

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
):
    """
    Single-month or single-day expense summary with category breakdown,
    budget tracking, and spending stats.

    IMPORTANT: Use this ONLY when the date range falls within a single calendar month
    (e.g. today, this week, this month). For queries spanning multiple months
    (e.g. "last 3 months", "May to July"), use the monthly_history tool instead.
    """
    session = await SessionRepository.get_session(get_session_id(ctx))
    if not session:
        return {
            "status": "unauthenticated",
            "message": "No active session. Please log in first using the google_login tool.",
        }
    active_email = session["email"]

    return await SummaryService.summarize(
        active_email,
        start_date,
        end_date,
        category,
    )


@mcp.tool()
async def monthly_history(
    ctx: Context,
    months: int = 3,
):
    """
    Use this tool when the user asks about spending across multiple months
    (e.g. "last 3 months", "show me May to July", "compare my spending").

    IMPORTANT: You MUST present the returned data to the user as a month-by-month
    bifurcation (e.g., separate breakdown for each month). Do NOT combine, aggregate,
    or sum the monthly values together into a single total range summary. Present
    each month's budget, income, spent, and savings individually.

    Args:
        months: Number of months to look back (default 3).
    """
    session = await SessionRepository.get_session(get_session_id(ctx))
    if not session:
        return {
            "status": "unauthenticated",
            "message": "No active session. Please log in first using the google_login tool.",
        }
    active_email = session["email"]

    return await SummaryService.monthly_history(
        active_email,
        months,
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
# Custom HTTP Routes for Google OAuth
# ---------------------------------------------------------

@mcp.custom_route("/", methods=["GET"])
async def root_redirect(request: Request) -> Response:
    return RedirectResponse(url="/sse")


@mcp.custom_route("/auth/google", methods=["GET"])
async def auth_google(request: Request) -> Response:
    from app.config import GOOGLE_CLIENT_ID, GOOGLE_REDIRECT_URI

    session_id = request.query_params.get("session_id")
    if not session_id:
        return HTMLResponse(
            "<h3>Missing session_id parameter in auth request.</h3>",
            status_code=400
        )

    if not GOOGLE_CLIENT_ID:
        return HTMLResponse(
            "<h3>Google OAuth is not configured on this server.</h3>"
            "<p>Please set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET environment variables.</p>",
            status_code=500
        )

    redirect_uri = GOOGLE_REDIRECT_URI or f"{request.url.scheme}://{request.headers.get('host')}/callback"

    google_auth_url = (
        "https://accounts.google.com/o/oauth2/v2/auth"
        f"?client_id={GOOGLE_CLIENT_ID}"
        f"&redirect_uri={redirect_uri}"
        "&response_type=code"
        "&scope=openid%20email%20profile"
        f"&state={session_id}"
        "&prompt=select_account"
    )
    return RedirectResponse(url=google_auth_url)


@mcp.custom_route("/callback", methods=["GET"])
async def oauth_callback(request: Request) -> Response:
    from app.config import GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_REDIRECT_URI

    code = request.query_params.get("code")
    session_id = request.query_params.get("state")  # state contains session_id

    if not code or not session_id:
        return HTMLResponse(
            "<h3>Authentication failed: Missing code or state parameters.</h3>",
            status_code=400
        )

    redirect_uri = GOOGLE_REDIRECT_URI or f"{request.url.scheme}://{request.headers.get('host')}/callback"

    # Exchange code for tokens
    async with httpx.AsyncClient() as client:
        try:
            token_response = await client.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "code": code,
                    "client_id": GOOGLE_CLIENT_ID,
                    "client_secret": GOOGLE_CLIENT_SECRET,
                    "redirect_uri": redirect_uri,
                    "grant_type": "authorization_code",
                }
            )
        except Exception as e:
            return HTMLResponse(
                f"<h3>Failed to contact Google Token Server: {str(e)}</h3>",
                status_code=500
            )

        if token_response.status_code != 200:
            return HTMLResponse(
                f"<h3>Google Token Exchange failed:</h3><pre>{token_response.text}</pre>",
                status_code=token_response.status_code
            )

        tokens = token_response.json()
        access_token = tokens.get("access_token")

        # Fetch user info using access token
        try:
            userinfo_response = await client.get(
                "https://www.googleapis.com/oauth2/v3/userinfo",
                headers={"Authorization": f"Bearer {access_token}"}
            )
        except Exception as e:
            return HTMLResponse(
                f"<h3>Failed to retrieve user info: {str(e)}</h3>",
                status_code=500
            )

        if userinfo_response.status_code != 200:
            return HTMLResponse(
                f"<h3>Google User Info failed:</h3><pre>{userinfo_response.text}</pre>",
                status_code=userinfo_response.status_code
            )

        userinfo = userinfo_response.json()
        email = userinfo.get("email")

        if not email:
            return HTMLResponse(
                "<h3>Authentication failed: Google did not return an email address.</h3>",
                status_code=400
            )

        normalized_email = email.strip().lower()

        # Associate user in DB
        user_id = await UserRepository.get_or_create_user(normalized_email)
        await SessionRepository.set_session(session_id, normalized_email, user_id)

        return HTMLResponse(
            f"""
            <html>
                <body style="font-family: sans-serif; text-align: center; padding: 50px; background-color: #f7f9fa;">
                    <div style="max-width: 500px; margin: auto; padding: 30px; background: white; border-radius: 8px; box-shadow: 0 4px 15px rgba(0,0,0,0.05);">
                        <h1 style="color: #4CAF50; font-size: 40px; margin-bottom: 10px;">🎉 Success!</h1>
                        <h2 style="color: #2c3e50; font-weight: normal; margin-top: 0;">Logged in as {normalized_email}</h2>
                        <hr style="border: 0; border-top: 1px solid #eee; margin: 20px 0;">
                        <p style="color: #7f8c8d; line-height: 1.6;">Your session is now authenticated. You can close this tab and go back to your chat assistant.</p>
                        <button onclick="window.close()" style="background-color: #4CAF50; color: white; border: none; padding: 10px 20px; border-radius: 4px; font-size: 16px; cursor: pointer; margin-top: 10px;">Close Window</button>
                    </div>
                </body>
            </html>
            """
        )


# ---------------------------------------------------------
# Run Server
# ---------------------------------------------------------

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))

    mcp.run(
        transport="http",
        path="/sse",
        host_origin_protection=False,
        host="0.0.0.0",
        port=port,
        middleware=[
            Middleware(ScopeMiddleware),
            Middleware(
                CORSMiddleware,
                allow_origins=["*"],
                allow_credentials=False,
                allow_methods=["*"],
                allow_headers=["*"],
            ),
        ],
    )