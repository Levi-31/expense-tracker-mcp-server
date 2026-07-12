import json
import os
import secrets
from datetime import datetime, timezone
from typing import Any
from pydantic import AnyUrl

from mcp.server.auth.provider import (
    AuthorizationCode,
    AuthorizationParams,
    AuthorizeError,
    OAuthAuthorizationServerProvider,
    RefreshToken,
    AccessToken,
    TokenError,
)
from mcp.shared.auth import OAuthClientInformationFull, OAuthToken
from app.databases import get_connection


class DatabaseOAuthProvider(OAuthAuthorizationServerProvider[AuthorizationCode, RefreshToken, AccessToken]):
    """
    PostgreSQL-backed implementation of MCP OAuth 2.0 Authorization Server Provider.
    """

    async def get_client(self, client_id: str) -> OAuthClientInformationFull | None:
        async with get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "SELECT client_info FROM oauth_clients WHERE client_id = %s",
                    (client_id,),
                )
                row = await cur.fetchone()
                if not row:
                    return None
                
                # Deserialization
                info_dict = json.loads(row["client_info"])
                return OAuthClientInformationFull.model_validate(info_dict)

    async def register_client(self, client_info: OAuthClientInformationFull) -> None:
        async with get_connection() as conn:
            async with conn.cursor() as cur:
                # Serialize client_info to JSON
                info_json = client_info.model_dump_json()
                await cur.execute(
                    """
                    INSERT INTO oauth_clients (client_id, client_info)
                    VALUES (%s, %s)
                    ON CONFLICT (client_id)
                    DO UPDATE SET client_info = EXCLUDED.client_info
                    """,
                    (client_info.client_id, info_json),
                )
            await conn.commit()

    async def authorize(self, client: OAuthClientInformationFull, params: AuthorizationParams) -> str:
        # 1. Generate local auth code
        code = secrets.token_urlsafe(32)

        # 2. Save auth code details to DB
        async with get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    INSERT INTO oauth_auth_codes (
                        code, client_id, redirect_uri, code_challenge, state, scopes, expires_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, NOW() + INTERVAL '10 minutes')
                    """,
                    (
                        code,
                        client.client_id,
                        str(params.redirect_uri),
                        params.code_challenge,
                        params.state,
                        json.dumps(params.scopes or []),
                    ),
                )
            await conn.commit()

        # 3. Redirect the browser to our /auth/google login initiation page,
        #    using the generated auth code as the session state.
        public_url = os.getenv("PUBLIC_URL")
        if not public_url:
            raise AuthorizeError(
                error="server_error",
                error_description="Server configuration error: PUBLIC_URL environment variable is missing.",
            )

        return f"{public_url.rstrip('/')}/auth/google?session_id={code}"

    async def load_authorization_code(
        self, client: OAuthClientInformationFull, authorization_code: str
    ) -> AuthorizationCode | None:
        async with get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    SELECT code, client_id, redirect_uri, code_challenge, email, scopes, expires_at, used
                    FROM oauth_auth_codes
                    WHERE code = %s AND client_id = %s
                    """,
                    (authorization_code, client.client_id),
                )
                row = await cur.fetchone()
                if not row or row["used"]:
                    return None

                # Return standard AuthorizationCode class
                return AuthorizationCode(
                    code=row["code"],
                    scopes=json.loads(row["scopes"]),
                    expires_at=row["expires_at"].timestamp(),
                    client_id=row["client_id"],
                    code_challenge=row["code_challenge"],
                    redirect_uri=AnyUrl(row["redirect_uri"]),
                    redirect_uri_provided_explicitly=True,
                    resource=None,
                    subject=row["email"], # Pass down the authenticated email
                )

    async def exchange_authorization_code(
        self, client: OAuthClientInformationFull, authorization_code: AuthorizationCode
    ) -> OAuthToken:
        if not authorization_code.subject:
            raise TokenError(
                error="invalid_grant",
                error_description="User has not authenticated this authorization code.",
            )

        # 1. Mark authorization code as used
        async with get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "UPDATE oauth_auth_codes SET used = TRUE WHERE code = %s",
                    (authorization_code.code,),
                )
            await conn.commit()

        # 2. Generate Access and Refresh Tokens
        access_token = f"at_{secrets.token_urlsafe(32)}"
        refresh_token = f"rt_{secrets.token_urlsafe(32)}"

        # 1 hour expiration for access token
        access_expires = datetime.now(timezone.utc) + timedelta_hours(1)
        # 30 days expiration for refresh token
        refresh_expires = datetime.now(timezone.utc) + timedelta_days(30)

        async with get_connection() as conn:
            async with conn.cursor() as cur:
                # Save access token
                await cur.execute(
                    """
                    INSERT INTO oauth_tokens (token, client_id, token_type, email, scopes, expires_at)
                    VALUES (%s, %s, 'access', %s, %s, %s)
                    """,
                    (
                        access_token,
                        client.client_id,
                        authorization_code.subject,
                        json.dumps(authorization_code.scopes),
                        access_expires,
                    ),
                )
                # Save refresh token
                await cur.execute(
                    """
                    INSERT INTO oauth_tokens (token, client_id, token_type, email, scopes, expires_at)
                    VALUES (%s, %s, 'refresh', %s, %s, %s)
                    """,
                    (
                        refresh_token,
                        client.client_id,
                        authorization_code.subject,
                        json.dumps(authorization_code.scopes),
                        refresh_expires,
                    ),
                )
            await conn.commit()

        return OAuthToken(
            access_token=access_token,
            token_type="Bearer",
            expires_in=3600,
            scope=" ".join(authorization_code.scopes),
            refresh_token=refresh_token,
        )

    async def load_refresh_token(self, client: OAuthClientInformationFull, refresh_token: str) -> RefreshToken | None:
        async with get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    SELECT token, client_id, email, scopes, expires_at
                    FROM oauth_tokens
                    WHERE token = %s AND client_id = %s AND token_type = 'refresh'
                    """,
                    (refresh_token, client.client_id),
                )
                row = await cur.fetchone()
                if not row:
                    return None

                # Check expiration
                if row["expires_at"] and row["expires_at"] < datetime.now(timezone.utc):
                    return None

                return RefreshToken(
                    token=row["token"],
                    client_id=row["client_id"],
                    scopes=json.loads(row["scopes"]),
                    expires_at=int(row["expires_at"].timestamp()) if row["expires_at"] else None,
                    subject=row["email"],
                )

    async def exchange_refresh_token(
        self,
        client: OAuthClientInformationFull,
        refresh_token: RefreshToken,
        scopes: list[str],
    ) -> OAuthToken:
        # Revoke the old refresh token
        await self.revoke_token(refresh_token.token)

        # Generate a new token pair
        new_access_token = f"at_{secrets.token_urlsafe(32)}"
        new_refresh_token = f"rt_{secrets.token_urlsafe(32)}"

        access_expires = datetime.now(timezone.utc) + timedelta_hours(1)
        refresh_expires = datetime.now(timezone.utc) + timedelta_days(30)

        async with get_connection() as conn:
            async with conn.cursor() as cur:
                # Save access token
                await cur.execute(
                    """
                    INSERT INTO oauth_tokens (token, client_id, token_type, email, scopes, expires_at)
                    VALUES (%s, %s, 'access', %s, %s, %s)
                    """,
                    (
                        new_access_token,
                        client.client_id,
                        refresh_token.subject,
                        json.dumps(scopes),
                        access_expires,
                    ),
                )
                # Save refresh token
                await cur.execute(
                    """
                    INSERT INTO oauth_tokens (token, client_id, token_type, email, scopes, expires_at)
                    VALUES (%s, %s, 'refresh', %s, %s, %s)
                    """,
                    (
                        new_refresh_token,
                        client.client_id,
                        refresh_token.subject,
                        json.dumps(scopes),
                        refresh_expires,
                    ),
                )
            await conn.commit()

        return OAuthToken(
            access_token=new_access_token,
            token_type="Bearer",
            expires_in=3600,
            scope=" ".join(scopes),
            refresh_token=new_refresh_token,
        )

    async def load_access_token(self, token: str) -> AccessToken | None:
        async with get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    SELECT token, client_id, email, scopes, expires_at
                    FROM oauth_tokens
                    WHERE token = %s AND token_type = 'access'
                    """,
                    (token,),
                )
                row = await cur.fetchone()
                if not row:
                    return None

                # Check expiration
                if row["expires_at"] and row["expires_at"] < datetime.now(timezone.utc):
                    return None

                return AccessToken(
                    token=row["token"],
                    client_id=row["client_id"],
                    scopes=json.loads(row["scopes"]),
                    expires_at=int(row["expires_at"].timestamp()) if row["expires_at"] else None,
                    subject=row["email"],
                )

    async def revoke_token(self, token: str) -> None:
        async with get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "DELETE FROM oauth_tokens WHERE token = %s",
                    (token,),
                )
            await conn.commit()


# Helper timedelta simulation
def timedelta_hours(h: int):
    import datetime as dt
    return dt.timedelta(hours=h)

def timedelta_days(d: int):
    import datetime as dt
    return dt.timedelta(days=d)
