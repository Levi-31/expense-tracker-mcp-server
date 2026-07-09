import asyncio
from datetime import date
from decimal import Decimal

from app.repository.expense_repository import ExpenseRepository
from app.repository.finance_repository import FinanceRepository
from app.repository.user_repository import UserRepository


class SummaryService:

    @staticmethod
    async def summarize(
        email: str,
        start_date: date,
        end_date: date,
        category: str | None = None,
    ) -> dict:

        user_id = await UserRepository.get_or_create_user(
            email,
        )

        month = start_date.replace(day=1)

        (
            category_summary,
            summary,
            finance,
            borrowed_data,
        ) = await asyncio.gather(

            ExpenseRepository.category_summary(
                user_id,
                start_date,
                end_date,
                category,
                exclude_borrowed=True,
            ),

            ExpenseRepository.summary_stats(
                user_id,
                start_date,
                end_date,
                exclude_borrowed=True,
            ),

            FinanceRepository.get_month(
                user_id,
                month,
            ),

            ExpenseRepository.borrowed_summary(
                user_id,
                start_date,
                end_date,
            ),
        )

        total_expense = summary["total_expense"]
        transactions = summary["transactions"]
        average_transaction = summary["average_transaction"]

        total_borrowed = borrowed_data["total_borrowed"] or Decimal("0")
        total_settled = borrowed_data["total_settled"] or Decimal("0")

        budget = Decimal("0")
        credit = Decimal("0")

        if finance:

            budget = finance["budget"] or Decimal("0")
            credit = finance["credit"] or Decimal("0")

        remaining_budget = budget - total_expense
        remaining_credit = credit - total_expense

        over_budget = False
        over_budget_amount = Decimal("0")
        budget_used_percent = Decimal("0")

        if budget > 0:

            budget_used_percent = round(
                (total_expense / budget) * 100,
                2,
            )

            if total_expense > budget:

                over_budget = True

                over_budget_amount = (
                    total_expense - budget
                )

        total_days = max(
            1,
            (end_date - start_date).days + 1,
        )

        average_daily_spend = round(
            total_expense / total_days,
            2,
        )

        # Convert category_summary to list and append borrowed and repaid if they exist
        cat_summary_list = [
            {
                "category": row["category"],
                "total_amount": float(
                    row["total_amount"]
                ),
            }
            for row in category_summary
        ]

        if total_borrowed > 0:
            cat_summary_list.append({
                "category": "borrowed",
                "total_amount": float(total_borrowed),
            })

        if total_settled > 0:
            cat_summary_list.append({
                "category": "repaid",
                "total_amount": float(total_settled),
            })

        # Sort descending
        cat_summary_list.sort(key=lambda x: x["total_amount"], reverse=True)

        largest_category = None
        largest_amount = Decimal("0")

        if cat_summary_list:
            largest_category = cat_summary_list[0]["category"]
            largest_amount = Decimal(str(cat_summary_list[0]["total_amount"]))

        return {

            "status": "ok",

            "month": month.strftime("%Y-%m"),

            "budget": float(budget),

            "credit": float(credit),

            "total_expense": float(total_expense),

            "total_borrowed": float(total_borrowed),

            "total_repaid": float(total_settled),

            "remaining_budget": float(
                remaining_budget
            ),

            "remaining_credit": float(
                remaining_credit
            ),

            "budget_used_percent": float(
                budget_used_percent
            ),

            "is_over_budget": over_budget,

            "over_budget_amount": float(
                over_budget_amount
            ),

            "transactions": transactions,

            "average_transaction": float(
                average_transaction
            ),

            "average_daily_spend": float(
                average_daily_spend
            ),

            "largest_category": largest_category,

            "largest_category_amount": float(
                largest_amount
            ),

            "category_summary": cat_summary_list,
        }