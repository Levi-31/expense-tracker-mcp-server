from uuid import UUID

from app.databases import get_connection


class UserRepository:

    @staticmethod
    def _normalize(email: str) -> str:
        """
        Lowercase and strip whitespace so that
        'User@Gmail.com' and 'user@gmail.com'
        resolve to the same user.
        """
        return email.strip().lower()

    @staticmethod
    async def get_by_email(
        email: str,
    ) -> dict | None:
        """
        Fetch a user row by email.
        Returns None if the user does not exist.
        """

        email = UserRepository._normalize(email)

        async with get_connection() as conn:

            async with conn.cursor() as cur:

                await cur.execute(
                    """
                    SELECT
                        id,
                        email,
                        full_name,
                        created_at
                    FROM users
                    WHERE email = %s
                    """,
                    (email,),
                )

                return await cur.fetchone()

    @staticmethod
    async def create_user(
        email: str,
        full_name: str = "",
    ) -> UUID:
        """
        Insert a new user and return the generated UUID.
        Raises on duplicate email.
        """

        email = UserRepository._normalize(email)

        async with get_connection() as conn:

            async with conn.cursor() as cur:

                await cur.execute(
                    """
                    INSERT INTO users
                    (
                        email,
                        full_name
                    )
                    VALUES
                    (
                        %s,
                        %s
                    )
                    RETURNING id
                    """,
                    (
                        email,
                        full_name,
                    ),
                )

                row = await cur.fetchone()

            await conn.commit()

        return row["id"]

    @staticmethod
    async def get_or_create_user(
        email: str,
        full_name: str = "",
    ) -> UUID:
        """
        Return the UUID for an existing user,
        or create a new one atomically.

        Uses INSERT ... ON CONFLICT DO NOTHING
        followed by a SELECT to handle race conditions.
        """

        email = UserRepository._normalize(email)

        async with get_connection() as conn:

            async with conn.cursor() as cur:

                await cur.execute(
                    """
                    INSERT INTO users
                    (
                        email,
                        full_name
                    )
                    VALUES
                    (
                        %s,
                        %s
                    )
                    ON CONFLICT (email)
                    DO NOTHING
                    """,
                    (
                        email,
                        full_name,
                    ),
                )

                await cur.execute(
                    """
                    SELECT id
                    FROM users
                    WHERE email = %s
                    """,
                    (email,),
                )

                row = await cur.fetchone()

            await conn.commit()

        return row["id"]
