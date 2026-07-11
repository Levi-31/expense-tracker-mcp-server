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
        import calendar
        month_last_day = calendar.monthrange(start_date.year, start_date.month)[1]
        month_end = start_date.replace(day=month_last_day)

        (
            category_summary,
            summary,
            finance,
            borrowed_data,
            month_total,
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

            # Full calendar month total (for budget tracking)
            ExpenseRepository.get_total(
                user_id,
                month,
                month_end,
                exclude_borrowed=True,
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

        # Budget/savings remaining always uses the full month's spend
        remaining_budget = budget - month_total
        savings = credit - month_total

        over_budget = False
        over_budget_amount = Decimal("0")
        budget_used_percent = Decimal("0")

        if budget > 0:

            budget_used_percent = round(
                (month_total / budget) * 100,
                2,
            )

            if month_total > budget:

                over_budget = True

                over_budget_amount = (
                    month_total - budget
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

            "income": float(credit),

            "total_expense": float(total_expense),

            "total_borrowed": float(total_borrowed),

            "total_repaid": float(total_settled),

            "remaining_budget": float(
                remaining_budget
            ),

            "savings": float(
                savings
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

    @staticmethod
    async def monthly_history(
        email: str,
        months: int = 3,
    ) -> dict:
        """
        Returns a per-month breakdown of budget, income (salary), total spend,
        credit card usage, savings, borrowed, and repaid for the last N months.
        Months with no data are clearly marked.
        """
        import calendar
        from datetime import date as date_type

        user_id = await UserRepository.get_or_create_user(email)

        today = date_type.today()

        # Build list of month-start dates going back N months
        month_dates = []
        current = today.replace(day=1)
        for _ in range(months):
            month_dates.append(current)
            if current.month == 1:
                current = current.replace(year=current.year - 1, month=12)
            else:
                current = current.replace(month=current.month - 1)

        month_dates.reverse()  # oldest first

        # Build parallel tasks for each month
        tasks = []
        for m in month_dates:
            last_day = calendar.monthrange(m.year, m.month)[1]
            m_end = m.replace(day=last_day)

            tasks.append(ExpenseRepository.get_total(user_id, m, m_end, exclude_borrowed=True))
            tasks.append(ExpenseRepository.get_credit_card_total(user_id, m, m_end))
            tasks.append(ExpenseRepository.borrowed_summary(user_id, m, m_end))
            tasks.append(FinanceRepository.get_month(user_id, m))

        results = await asyncio.gather(*tasks)

        breakdown = []
        idx = 0
        for m in month_dates:
            total_spent = results[idx]
            cc_spent = results[idx + 1]
            borrowed_data = results[idx + 2]
            finance = results[idx + 3]
            idx += 4

            total_borrowed = borrowed_data["total_borrowed"] or Decimal("0")
            total_repaid = borrowed_data["total_settled"] or Decimal("0")

            has_expenses = total_spent > 0 or cc_spent > 0 or total_borrowed > 0
            has_finance = finance is not None

            if not has_expenses and not has_finance:
                breakdown.append({
                    "month": m.strftime("%Y-%m"),
                    "status": "no_data",
                    "message": "No expenses or budget configured for this month.",
                })
                continue

            budget = Decimal("0")
            credit = Decimal("0")
            if finance:
                budget = finance["budget"] or Decimal("0")
                credit = finance["credit"] or Decimal("0")

            entry = {
                "month": m.strftime("%Y-%m"),
                "status": "ok",
                "total_spent": float(total_spent),
                "credit_card_spent": float(cc_spent),
                "total_borrowed": float(total_borrowed),
                "total_repaid": float(total_repaid),
            }

            if has_finance:
                entry["budget"] = float(budget)
                entry["income"] = float(credit)
                entry["remaining_budget"] = float(budget - total_spent)
                entry["savings"] = float(credit - total_spent)
            else:
                entry["budget"] = "not_set"
                entry["income"] = "not_set"

            breakdown.append(entry)

        return {
            "status": "ok",
            "months_covered": months,
            "breakdown": breakdown,
        }