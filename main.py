from contextlib import asynccontextmanager
from decimal import Decimal
from datetime import date
import os
import httpx

from mcp.server.fastmcp import FastMCP, Context
from starlette.requests import Request
from starlette.responses import HTMLResponse, RedirectResponse, Response
from starlette.applications import Starlette

from app.databases import open_pool, close_pool, get_connection
from app.schema import init_db
from app.resources import get_categories

from app.models import ExpenseCreate

from app.services.expense_service import ExpenseService
from app.services.finance_service import FinanceService
from app.services.summary_service import SummaryService
from app.repository.user_repository import UserRepository
from app.repository.session_repository import SessionRepository
import uuid
from starlette.datastructures import QueryParams
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware

# MCP OAuth Imports
from app.auth.oauth_provider import DatabaseOAuthProvider
from mcp.server.auth.provider import ProviderTokenVerifier
from mcp.server.auth.settings import AuthSettings, ClientRegistrationOptions
from pydantic import AnyHttpUrl


def get_authenticated_email(ctx: Context) -> str:
    """
    Extract the authenticated user email from the OAuth Bearer token scope.
    Since RequireAuthMiddleware is active, it guarantees the user is authenticated.
    """
    request_ctx = getattr(ctx, "request_context", None)
    if request_ctx is not None:
        request = getattr(request_ctx, "request", None)
        if request is not None:
            user = request.scope.get("user")
            if user and hasattr(user, "access_token") and user.access_token:
                if user.access_token.subject:
                    return user.access_token.subject
    raise RuntimeError("User is not authenticated.")


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

class CustomFastMCP(FastMCP):
    def streamable_http_app(self) -> Starlette:
        app = super().streamable_http_app()
        original_lifespan = app.router.lifespan_context

        @asynccontextmanager
        async def combined_lifespan(app_instance: Starlette):
            await open_pool()
            await init_db()
            print("✅ PostgreSQL pool initialized via HTTP lifespan.")
            try:
                async with original_lifespan(app_instance):
                    yield
            finally:
                await close_pool()
                print("✅ PostgreSQL pool closed via HTTP lifespan.")

        app.router.lifespan_context = combined_lifespan
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=False,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        return app

    def sse_app(self, mount_path: str | None = None) -> Starlette:
        app = super().sse_app(mount_path)

        @asynccontextmanager
        async def sse_lifespan(app_instance: Starlette):
            await open_pool()
            await init_db()
            print("✅ PostgreSQL pool initialized via SSE lifespan.")
            try:
                yield
            finally:
                await close_pool()
                print("✅ PostgreSQL pool closed via SSE lifespan.")

        app.router.lifespan_context = sse_lifespan
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=False,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        return app
port = int(os.getenv("PORT", "8000"))
public_url = os.getenv("PUBLIC_URL") or "https://expense-tracker-mcp-404722039668.asia-south1.run.app"
oauth_provider = DatabaseOAuthProvider()

mcp = CustomFastMCP(
    "Expense Tracker",
    instructions=(
        "The user must be authenticated. The client will automatically prompt the user to sign in natively.\n\n"
        "CRITICAL RULE: Whenever a credit card expense is being added (or using the 'credit_card_usage' category), "
        "if the user has not specified whether it is for self-use or borrowed by a friend, you MUST ask the user "
        "for clarification (e.g. 'Is this credit card expense for self-use or was it borrowed by a friend?') "
        "before invoking the add_expense tool."
    ),
    lifespan=lifespan,
    host="0.0.0.0",
    port=port,
    streamable_http_path="/sse",
    auth_server_provider=oauth_provider,
    auth=AuthSettings(
        issuer_url=AnyHttpUrl(public_url),
        resource_server_url=AnyHttpUrl(public_url),
        client_registration_options=ClientRegistrationOptions(enabled=True),
    ),
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
async def get_current_user(
    ctx: Context,
) -> dict:
    """
    Returns the currently logged-in user email.
    """
    email = get_authenticated_email(ctx)
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
    active_email = get_authenticated_email(ctx)

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
    active_email = get_authenticated_email(ctx)

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
    active_email = get_authenticated_email(ctx)

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
    active_email = get_authenticated_email(ctx)

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
    active_email = get_authenticated_email(ctx)

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
    active_email = get_authenticated_email(ctx)

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
    active_email = get_authenticated_email(ctx)

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
    active_email = get_authenticated_email(ctx)

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
    active_email = get_authenticated_email(ctx)

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
    active_email = get_authenticated_email(ctx)

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
    active_email = get_authenticated_email(ctx)

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
    from mcp.server.auth.provider import construct_redirect_uri

    code = request.query_params.get("code")
    session_id = request.query_params.get("state")  # state contains session_id (which is our auth_code)

    if not code or not session_id:
        return HTMLResponse(
            "<h3>Authentication failed: Missing code or state parameters.</h3>",
            status_code=400
        )

    # 1. Fetch parameters from our oauth_auth_codes table to get redirect_uri and state
    async with get_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT redirect_uri, state
                FROM oauth_auth_codes
                WHERE code = %s AND expires_at > NOW() AND used = FALSE
                """,
                (session_id,),
            )
            row = await cur.fetchone()
            if not row:
                return HTMLResponse(
                    "<h3>Session expired or invalid. Please close this window and try logging in again.</h3>",
                    status_code=400
                )
            redirect_uri = row["redirect_uri"]
            original_client_state = row["state"]

    google_redirect_uri = GOOGLE_REDIRECT_URI or f"{request.url.scheme}://{request.headers.get('host')}/callback"

    # Exchange code for tokens with Google
    async with httpx.AsyncClient() as client:
        try:
            token_response = await client.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "code": code,
                    "client_id": GOOGLE_CLIENT_ID,
                    "client_secret": GOOGLE_CLIENT_SECRET,
                    "redirect_uri": google_redirect_uri,
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

        # Update the auth code in DB with the user's email, and ensure the user exists
        await UserRepository.get_or_create_user(normalized_email)
        async with get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "UPDATE oauth_auth_codes SET email = %s WHERE code = %s",
                    (normalized_email, session_id),
                )
            await conn.commit()

        # Redirect the browser back to the MCP client redirect URI (e.g. Claude / ChatGPT)
        # Passing the session_id as the authorization code, and the original client state
        redirect_url = construct_redirect_uri(redirect_uri, code=session_id, state=original_client_state)
        return RedirectResponse(url=redirect_url)


# ---------------------------------------------------------
# Run Server
# ---------------------------------------------------------

if __name__ == "__main__":
    mcp.run(transport="streamable-http")