from datetime import date
from decimal import Decimal
from uuid import UUID

from app.databases import get_connection


class FinanceRepository:

    @staticmethod
    async def upsert_budget(
        user_id: UUID,
        month: date,
        budget: Decimal,
    ) -> None:

        async with get_connection() as conn:

            async with conn.cursor() as cur:

                await cur.execute(
                    """
                    INSERT INTO monthly_finance
                    (
                        user_id,
                        month,
                        budget
                    )
                    VALUES
                    (
                        %s,
                        %s,
                        %s
                    )
                    ON CONFLICT (user_id, month)
                    DO UPDATE
                    SET
                        budget = EXCLUDED.budget
                    """,
                    (
                        user_id,
                        month,
                        budget,
                    ),
                )

            await conn.commit()

    @staticmethod
    async def upsert_credit(
        user_id: UUID,
        month: date,
        credit: Decimal,
    ) -> None:

        async with get_connection() as conn:

            async with conn.cursor() as cur:

                await cur.execute(
                    """
                    INSERT INTO monthly_finance
                    (
                        user_id,
                        month,
                        credit
                    )
                    VALUES
                    (
                        %s,
                        %s,
                        %s
                    )
                    ON CONFLICT (user_id, month)
                    DO UPDATE
                    SET
                        credit = EXCLUDED.credit
                    """,
                    (
                        user_id,
                        month,
                        credit,
                    ),
                )

            await conn.commit()

    @staticmethod
    async def get_month(
        user_id: UUID,
        month: date,
    ) -> dict | None:

        async with get_connection() as conn:

            async with conn.cursor() as cur:

                await cur.execute(
                    """
                    SELECT
                        month,
                        budget,
                        credit
                    FROM monthly_finance
                    WHERE user_id = %s
                      AND month = %s
                    """,
                    (
                        user_id,
                        month,
                    ),
                )

                return await cur.fetchone()