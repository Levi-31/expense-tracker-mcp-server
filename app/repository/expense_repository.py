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
        is_borrowed: bool = False,
        is_settled: bool = False,
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
                        note,
                        is_borrowed,
                        is_settled
                    )
                    VALUES
                    (
                        %s,
                        %s,
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
                        is_borrowed,
                        is_settled,
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
        exclude_borrowed: bool = False,
    ) -> list[dict]:

        sql = """
        SELECT
            id,
            date,
            amount,
            category,
            subcategory,
            note,
            is_borrowed,
            is_settled
        FROM expenses
        WHERE user_id = %s
          AND date BETWEEN %s AND %s
        """
        params = [user_id, start_date, end_date]

        if exclude_borrowed:
            sql += " AND is_borrowed = FALSE"

        sql += " ORDER BY date, id"

        async with get_connection() as conn:

            async with conn.cursor() as cur:

                await cur.execute(sql, params)

                return await cur.fetchall()

    @staticmethod
    async def get_total(
        user_id: UUID,
        start_date: date,
        end_date: date,
        exclude_borrowed: bool = True,
    ) -> Decimal:

        sql = """
        SELECT
        COALESCE(SUM(amount),0) AS total
        FROM expenses
        WHERE user_id = %s
          AND date BETWEEN %s AND %s
        """
        params = [user_id, start_date, end_date]

        if exclude_borrowed:
            sql += " AND is_borrowed = FALSE"

        async with get_connection() as conn:

            async with conn.cursor() as cur:

                await cur.execute(sql, params)

                row = await cur.fetchone()

        return row["total"]

    @staticmethod
    async def category_summary(
        user_id: UUID,
        start_date: date,
        end_date: date,
        category: str | None = None,
        exclude_borrowed: bool = True,
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

        if exclude_borrowed:
            sql += " AND is_borrowed = FALSE"

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
        is_borrowed: bool = False,
        is_settled: bool = False,
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
                        note = %s,
                        is_borrowed = %s,
                        is_settled = %s
                    WHERE id = %s
                      AND user_id = %s
                    """,
                    (
                        expense_date,
                        amount,
                        category,
                        subcategory,
                        note,
                        is_borrowed,
                        is_settled,
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
        exclude_borrowed: bool = False,
    ) -> list[dict]:

        sql = """
        SELECT
            id,
            date,
            amount,
            category,
            subcategory,
            note,
            is_borrowed,
            is_settled
        FROM expenses
        WHERE user_id = %s
        """
        params = [user_id]

        if exclude_borrowed:
            sql += " AND is_borrowed = FALSE"

        sql += """
        ORDER BY
            date DESC,
            id DESC
        LIMIT %s
        """
        params.append(limit)

        async with get_connection() as conn:

            async with conn.cursor() as cur:

                await cur.execute(sql, params)

                return await cur.fetchall()

    @staticmethod
    async def summary_stats(
        user_id: UUID,
        start_date: date,
        end_date: date,
        exclude_borrowed: bool = True,
    ) -> dict:
        """
        Returns overall statistics in a single query.
        """

        sql = """
        SELECT

            COUNT(*) AS transactions,

            COALESCE(SUM(amount),0)
                AS total_expense,

            COALESCE(AVG(amount),0)
                AS average_transaction

        FROM expenses

        WHERE user_id = %s
          AND date BETWEEN %s AND %s
        """
        params = [user_id, start_date, end_date]

        if exclude_borrowed:
            sql += " AND is_borrowed = FALSE"

        async with get_connection() as conn:

            async with conn.cursor() as cur:

                await cur.execute(sql, params)

                return await cur.fetchone()

    @staticmethod
    async def borrowed_summary(
        user_id: UUID,
        start_date: date,
        end_date: date,
    ) -> dict:
        """
        Returns stats for borrowed expenses, separating outstanding and settled amounts.
        """
        async with get_connection() as conn:

            async with conn.cursor() as cur:

                await cur.execute(
                    """
                    SELECT
                        COALESCE(SUM(CASE WHEN is_settled = FALSE THEN amount ELSE 0 END), 0) AS total_borrowed,
                        COALESCE(SUM(CASE WHEN is_settled = TRUE THEN amount ELSE 0 END), 0) AS total_settled,
                        COUNT(*) AS total_transactions
                    FROM expenses
                    WHERE user_id = %s
                      AND date BETWEEN %s AND %s
                      AND is_borrowed = TRUE
                    """,
                    (user_id, start_date, end_date),
                )

                return await cur.fetchone()

    @staticmethod
    async def settle(
        user_id: UUID,
        expense_id: int,
        is_settled: bool = True,
    ) -> bool:
        """
        Mark a borrowed expense as settled (repaid).
        """
        async with get_connection() as conn:

            async with conn.cursor() as cur:

                await cur.execute(
                    """
                    UPDATE expenses
                    SET is_settled = %s
                    WHERE id = %s
                      AND user_id = %s
                      AND is_borrowed = TRUE
                    """,
                    (is_settled, expense_id, user_id),
                )

                updated = cur.rowcount

            await conn.commit()

        return updated > 0
