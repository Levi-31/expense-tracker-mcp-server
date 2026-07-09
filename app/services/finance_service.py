from datetime import datetime

from app.repository.finance_repository import FinanceRepository


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
        month: str,
        budget,
    ):

        month = cls.normalize_month(month)

        await FinanceRepository.upsert_budget(
            month,
            budget,
        )

        return {
            "status": "ok",
            "month": str(month),
            "budget": float(budget),
        }

    @classmethod
    async def set_credit(
        cls,
        month,
        credit,
    ):

        month = cls.normalize_month(month)

        await FinanceRepository.upsert_credit(
            month,
            credit,
        )

        return {
            "status": "ok",
            "month": str(month),
            "credit": float(credit),
        }

    @classmethod
    async def get_month(cls, month):

        month = cls.normalize_month(month)

        row = await FinanceRepository.get_month(month)

        if row is None:

            return {
                "month": str(month),
                "budget": 0,
                "credit": 0,
            }

        return {
            "month": str(row["month"]),
            "budget": float(row["budget"]),
            "credit": float(row["credit"]),
        }