from datetime import date
from decimal import Decimal

from app.databases import get_connection


class FinanceRepository:

    @staticmethod
    async def upsert_budget(
        month: date,
        budget: Decimal,
    ):

        async with get_connection() as conn:

            async with conn.cursor() as cur:

                await cur.execute(
                    """
                    INSERT INTO monthly_finance
                    (
                        month,
                        budget
                    )
                    VALUES
                    (
                        %s,
                        %s
                    )
                    ON CONFLICT(month)
                    DO UPDATE
                    SET
                        budget=EXCLUDED.budget
                    """,
                    (
                        month,
                        budget,
                    ),
                )

            await conn.commit()

    @staticmethod
    async def upsert_credit(
        month,
        credit,
    ):

        async with get_connection() as conn:

            async with conn.cursor() as cur:

                await cur.execute(
                    """
                    INSERT INTO monthly_finance
                    (
                        month,
                        credit
                    )
                    VALUES
                    (
                        %s,
                        %s
                    )
                    ON CONFLICT(month)
                    DO UPDATE
                    SET
                        credit=EXCLUDED.credit
                    """,
                    (
                        month,
                        credit,
                    ),
                )

            await conn.commit()

    @staticmethod
    async def get_month(
        month,
    ):

        async with get_connection() as conn:

            async with conn.cursor() as cur:

                await cur.execute(
                    """
                    SELECT
                        month,
                        budget,
                        credit
                    FROM monthly_finance
                    WHERE month=%s
                    """,
                    (
                        month,
                    ),
                )

                return await cur.fetchone()