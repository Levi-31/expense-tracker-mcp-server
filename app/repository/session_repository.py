from uuid import UUID
from app.databases import get_connection


class SessionRepository:

    @staticmethod
    async def set_session(session_id: str, email: str, user_id: UUID) -> None:
        async with get_connection() as conn:

            async with conn.cursor() as cur:

                await cur.execute(
                    """
                    INSERT INTO user_sessions (session_id, email, user_id, updated_at)
                    VALUES (%s, %s, %s, NOW())
                    ON CONFLICT (session_id)
                    DO UPDATE SET email = EXCLUDED.email, user_id = EXCLUDED.user_id, updated_at = NOW()
                    """,
                    (session_id, email, str(user_id)),
                )

            await conn.commit()

    @staticmethod
    async def get_session(session_id: str) -> dict | None:
        async with get_connection() as conn:

            async with conn.cursor() as cur:

                await cur.execute(
                    "SELECT email, user_id FROM user_sessions WHERE session_id = %s",
                    (session_id,),
                )

                row = await cur.fetchone()
                if not row:
                    return None

                return {
                    "email": row["email"],
                    "user_id": row["user_id"],
                }

    @staticmethod
    async def delete_session(session_id: str) -> None:
        async with get_connection() as conn:

            async with conn.cursor() as cur:

                await cur.execute(
                    "DELETE FROM user_sessions WHERE session_id = %s",
                    (session_id,),
                )

            await conn.commit()
