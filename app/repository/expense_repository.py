from datetime import date
from decimal import Decimal
from uuid import UUID

from app.databases import get_connection


class ExpenseRepository:

    @staticmethod
    async def add(
        user_id: UUID,
        expense_date: date,
        amount: Decimal,
        category: str,
        subcategory: str,
        note: str,
    ) -> int:

        async with get_connection() as conn:

            async with conn.cursor() as cur:

                await cur.execute(
                    """
                    INSERT INTO expenses
                    (
                        user_id,
                        date,
                        amount,
                        category,
                        subcategory,
                        note
                    )
                    VALUES
                    (
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s
                    )
                    RETURNING id
                    """,
                    (
                        user_id,
                        expense_date,
                        amount,
                        category,
                        subcategory,
                        note,
                    ),
                )

                row = await cur.fetchone()

            await conn.commit()

        return row["id"]

    @staticmethod
    async def list_between(
        user_id: UUID,
        start_date: date,
        end_date: date,
    ) -> list[dict]:

        async with get_connection() as conn:

            async with conn.cursor() as cur:

                await cur.execute(
                    """
                    SELECT
                        id,
                        date,
                        amount,
                        category,
                        subcategory,
                        note
                    FROM expenses
                    WHERE user_id = %s
                      AND date BETWEEN %s AND %s
                    ORDER BY date, id
                    """,
                    (
                        user_id,
                        start_date,
                        end_date,
                    ),
                )

                return await cur.fetchall()

    @staticmethod
    async def get_total(
        user_id: UUID,
        start_date: date,
        end_date: date,
    ) -> Decimal:

        async with get_connection() as conn:

            async with conn.cursor() as cur:

                await cur.execute(
                    """
                    SELECT
                    COALESCE(SUM(amount),0) AS total
                    FROM expenses
                    WHERE user_id = %s
                      AND date BETWEEN %s AND %s
                    """,
                    (
                        user_id,
                        start_date,
                        end_date,
                    ),
                )

                row = await cur.fetchone()

        return row["total"]

    @staticmethod
    async def category_summary(
        user_id: UUID,
        start_date: date,
        end_date: date,
        category: str | None = None,
    ) -> list[dict]:
        """
        Returns category-wise total expense for a user.
        """

        sql = """
        SELECT
            category,
            SUM(amount) AS total_amount
        FROM expenses
        WHERE user_id = %s
          AND date BETWEEN %s AND %s
        """

        params: list = [
            user_id,
            start_date,
            end_date,
        ]

        if category:

            sql += " AND category = %s"

            params.append(category)

        sql += """
        GROUP BY category
        ORDER BY total_amount DESC
        """

        async with get_connection() as conn:

            async with conn.cursor() as cur:

                await cur.execute(sql, params)

                return await cur.fetchall()

    @staticmethod
    async def delete(
        user_id: UUID,
        expense_id: int,
    ) -> bool:

        async with get_connection() as conn:

            async with conn.cursor() as cur:

                await cur.execute(
                    """
                    DELETE FROM expenses
                    WHERE id = %s
                      AND user_id = %s
                    """,
                    (
                        expense_id,
                        user_id,
                    ),
                )

                deleted = cur.rowcount

            await conn.commit()

        return deleted > 0

    @staticmethod
    async def update(
        user_id: UUID,
        expense_id: int,
        expense_date: date,
        amount: Decimal,
        category: str,
        subcategory: str,
        note: str,
    ) -> bool:

        async with get_connection() as conn:

            async with conn.cursor() as cur:

                await cur.execute(
                    """
                    UPDATE expenses
                    SET
                        date = %s,
                        amount = %s,
                        category = %s,
                        subcategory = %s,
                        note = %s
                    WHERE id = %s
                      AND user_id = %s
                    """,
                    (
                        expense_date,
                        amount,
                        category,
                        subcategory,
                        note,
                        expense_id,
                        user_id,
                    ),
                )

                updated = cur.rowcount

            await conn.commit()

        return updated > 0

    @staticmethod
    async def recent(
        user_id: UUID,
        limit: int = 10,
    ) -> list[dict]:

        async with get_connection() as conn:

            async with conn.cursor() as cur:

                await cur.execute(
                    """
                    SELECT
                        id,
                        date,
                        amount,
                        category,
                        subcategory,
                        note
                    FROM expenses
                    WHERE user_id = %s
                    ORDER BY
                        date DESC,
                        id DESC
                    LIMIT %s
                    """,
                    (
                        user_id,
                        limit,
                    ),
                )

                return await cur.fetchall()

    @staticmethod
    async def summary_stats(
        user_id: UUID,
        start_date: date,
        end_date: date,
    ) -> dict:
        """
        Returns overall statistics in a single query.
        """

        async with get_connection() as conn:

            async with conn.cursor() as cur:

                await cur.execute(
                    """
                    SELECT

                        COUNT(*) AS transactions,

                        COALESCE(SUM(amount),0)
                            AS total_expense,

                        COALESCE(AVG(amount),0)
                            AS average_transaction

                    FROM expenses

                    WHERE user_id = %s
                      AND date BETWEEN %s AND %s
                    """,
                    (
                        user_id,
                        start_date,
                        end_date,
                    ),
                )

                return await cur.fetchone()
