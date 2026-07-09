from uuid import UUID

from app.databases import get_connection


class UserRepository:

    @staticmethod
    async def get_by_username(
        username: str,
    ) -> dict | None:
        """
        Fetch a user row by username.
        Returns None if the user does not exist.
        """

        async with get_connection() as conn:

            async with conn.cursor() as cur:

                await cur.execute(
                    """
                    SELECT
                        id,
                        username,
                        full_name,
                        created_at
                    FROM users
                    WHERE username = %s
                    """,
                    (username,),
                )

                return await cur.fetchone()

    @staticmethod
    async def create_user(
        username: str,
        full_name: str = "",
    ) -> UUID:
        """
        Insert a new user and return the generated UUID.
        Raises on duplicate username.
        """

        async with get_connection() as conn:

            async with conn.cursor() as cur:

                await cur.execute(
                    """
                    INSERT INTO users
                    (
                        username,
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
                        username,
                        full_name,
                    ),
                )

                row = await cur.fetchone()

            await conn.commit()

        return row["id"]

    @staticmethod
    async def get_or_create_user(
        username: str,
        full_name: str = "",
    ) -> UUID:
        """
        Return the UUID for an existing user,
        or create a new one atomically.

        Uses INSERT ... ON CONFLICT DO NOTHING
        followed by a SELECT to handle race conditions.
        """

        async with get_connection() as conn:

            async with conn.cursor() as cur:

                await cur.execute(
                    """
                    INSERT INTO users
                    (
                        username,
                        full_name
                    )
                    VALUES
                    (
                        %s,
                        %s
                    )
                    ON CONFLICT (username)
                    DO NOTHING
                    """,
                    (
                        username,
                        full_name,
                    ),
                )

                await cur.execute(
                    """
                    SELECT id
                    FROM users
                    WHERE username = %s
                    """,
                    (username,),
                )

                row = await cur.fetchone()

            await conn.commit()

        return row["id"]
