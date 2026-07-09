from datetime import date
from decimal import Decimal

from app.databases import get_connection


class ExpenseRepository:

    @staticmethod
    async def add(
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
                        %s
                    )
                    RETURNING id
                    """,
                    (
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
        start_date: date,
        end_date: date,
    ):

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
                    WHERE date BETWEEN %s AND %s
                    ORDER BY date,id
                    """,
                    (
                        start_date,
                        end_date,
                    ),
                )

                return await cur.fetchall()

    @staticmethod
    async def get_total(
        start_date: date,
        end_date: date,
    ):

        async with get_connection() as conn:

            async with conn.cursor() as cur:

                await cur.execute(
                    """
                    SELECT
                    COALESCE(SUM(amount),0) AS total
                    FROM expenses
                    WHERE date BETWEEN %s AND %s
                    """,
                    (
                        start_date,
                        end_date,
                    ),
                )

                row = await cur.fetchone()

        return row["total"]

    @staticmethod
    async def category_summary(
        start_date: date,
        end_date: date,
        category: str | None = None,
    ):

        sql = """
        SELECT
            category,
            SUM(amount) AS total_amount
        FROM expenses
        WHERE date BETWEEN %s AND %s
        """

        params = [
            start_date,
            end_date,
        ]

        if category:

            sql += " AND category=%s"

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
        expense_id: int,
    ):

        async with get_connection() as conn:

            async with conn.cursor() as cur:

                await cur.execute(
                    """
                    DELETE FROM expenses
                    WHERE id=%s
                    """,
                    (
                        expense_id,
                    ),
                )

                deleted = cur.rowcount

            await conn.commit()

        return deleted > 0

    @staticmethod
    async def update(
        expense_id: int,
        expense_date,
        amount,
        category,
        subcategory,
        note,
    ):

        async with get_connection() as conn:

            async with conn.cursor() as cur:

                await cur.execute(
                    """
                    UPDATE expenses
                    SET
                        date=%s,
                        amount=%s,
                        category=%s,
                        subcategory=%s,
                        note=%s
                    WHERE id=%s
                    """,
                    (
                        expense_date,
                        amount,
                        category,
                        subcategory,
                        note,
                        expense_id,
                    ),
                )

                updated = cur.rowcount

            await conn.commit()

        return updated > 0

    @staticmethod
    async def recent(
        limit: int = 10,
    ):

        async with get_connection() as conn:

            async with conn.cursor() as cur:

                await cur.execute(
                    """
                    SELECT
                        *
                    FROM expenses
                    ORDER BY
                        date DESC,
                        id DESC
                    LIMIT %s
                    """,
                    (
                        limit,
                    ),
                )

                return await cur.fetchall()
            
    @staticmethod
    async def category_summary(
            start_date,
            end_date,
            category=None,
        ):
            """
            Returns category wise total expense.
            """

            query = """
            SELECT
                category,
                SUM(amount) AS total_amount
            FROM expenses
            WHERE date BETWEEN %s AND %s
            """

            params = [start_date, end_date]

            if category:
                query += " AND category=%s"
                params.append(category)

            query += """
            GROUP BY category
            ORDER BY total_amount DESC
            """

            async with get_connection() as conn:
                async with conn.cursor() as cur:

                    await cur.execute(query, params)

                    return await cur.fetchall()

    @staticmethod
    async def summary_stats(
            start_date,
            end_date,
        ):
            """
            Returns overall statistics in a single query.
            """

            async with get_connection() as conn:

                async with conn.cursor() as cur:

                    await cur.execute(
                        """
                        SELECT

                            COUNT(*) AS transactions,

                            COALESCE(SUM(amount),0) AS total_expense,

                            COALESCE(AVG(amount),0) AS average_transaction

                        FROM expenses

                        WHERE date BETWEEN %s AND %s
                        """,
                        (
                            start_date,
                            end_date,
                        ),
                    )

                    return await cur.fetchone()
