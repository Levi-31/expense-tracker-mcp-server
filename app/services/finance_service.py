from datetime import datetime
from decimal import Decimal

from app.repository.finance_repository import FinanceRepository
from app.repository.user_repository import UserRepository


class FinanceService:

    @staticmethod
    def normalize_month(month: str):

        return datetime.strptime(
            month,
            "%Y-%m",
        ).date().replace(day=1)

    @classmethod
    async def set_budget(
        cls,
        email: str,
        month: str,
        budget: Decimal,
    ) -> dict:

        user_id = await UserRepository.get_or_create_user(
            email,
        )

        month_date = cls.normalize_month(month)

        await FinanceRepository.upsert_budget(
            user_id,
            month_date,
            budget,
        )

        return {
            "status": "ok",
            "month": str(month_date),
            "budget": float(budget),
        }

    @classmethod
    async def set_credit(
        cls,
        email: str,
        month: str,
        credit: Decimal,
    ) -> dict:

        user_id = await UserRepository.get_or_create_user(
            email,
        )

        month_date = cls.normalize_month(month)

        await FinanceRepository.upsert_credit(
            user_id,
            month_date,
            credit,
        )

        return {
            "status": "ok",
            "month": str(month_date),
            "credit": float(credit),
        }

    @classmethod
    async def get_month(
        cls,
        email: str,
        month: str,
    ) -> dict:

        user_id = await UserRepository.get_or_create_user(
            email,
        )

        month_date = cls.normalize_month(month)

        row = await FinanceRepository.get_month(
            user_id,
            month_date,
        )

        if row is None:

            return {
                "month": str(month_date),
                "budget": 0,
                "credit": 0,
            }

        return {
            "month": str(row["month"]),
            "budget": float(row["budget"]),
            "credit": float(row["credit"]),
        }