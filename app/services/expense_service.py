from datetime import date

from app.models import ExpenseCreate
from app.repository.expense_repository import ExpenseRepository
from app.repository.user_repository import UserRepository
from app.resources import normalize_and_validate


class ExpenseService:

    @staticmethod
    async def add_expense(
        email: str,
        data: ExpenseCreate,
    ) -> dict:

        try:
            category, subcategory = normalize_and_validate(
                data.category,
                data.subcategory,
            )
        except ValueError as e:
            return {
                "status": "error",
                "message": str(e),
            }

        # Auto-detect is_borrowed
        is_borrowed = data.is_borrowed
        note_lower = data.note.lower()
        if (category == "credit_card_usage" and subcategory == "borrowed_to_friend") or \
           ("borrowed to a friend" in note_lower or "borrowed to friend" in note_lower or "lent to" in note_lower):
            is_borrowed = True

        user_id = await UserRepository.get_or_create_user(
            email,
        )

        expense_id = await ExpenseRepository.add(
            user_id=user_id,
            expense_date=data.date,
            amount=data.amount,
            category=category,
            subcategory=subcategory,
            note=data.note.strip(),
            is_borrowed=is_borrowed,
            is_settled=data.is_settled,
        )

        return {
            "status": "ok",
            "expense_id": expense_id,
        }

    @staticmethod
    async def list_expenses(
        email: str,
        start_date: date,
        end_date: date,
    ) -> dict:

        user_id = await UserRepository.get_or_create_user(
            email,
        )

        expenses = await ExpenseRepository.list_between(
            user_id,
            start_date,
            end_date,
        )

        return {
            "status": "ok",
            "count": len(expenses),
            "expenses": expenses,
        }

    @staticmethod
    async def delete_expense(
        email: str,
        expense_id: int,
    ) -> dict:

        user_id = await UserRepository.get_or_create_user(
            email,
        )

        deleted = await ExpenseRepository.delete(
            user_id,
            expense_id,
        )

        if not deleted:
            return {
                "status": "error",
                "message": "Expense not found.",
            }

        return {
            "status": "ok",
            "message": "Expense deleted successfully.",
        }

    @staticmethod
    async def update_expense(
        email: str,
        expense_id: int,
        data: ExpenseCreate,
    ) -> dict:

        try:
            category, subcategory = normalize_and_validate(
                data.category,
                data.subcategory,
            )
        except ValueError as e:
            return {
                "status": "error",
                "message": str(e),
            }

        # Auto-detect is_borrowed
        is_borrowed = data.is_borrowed
        note_lower = data.note.lower()
        if (category == "credit_card_usage" and subcategory == "borrowed_to_friend") or \
           ("borrowed to a friend" in note_lower or "borrowed to friend" in note_lower or "lent to" in note_lower):
            is_borrowed = True

        user_id = await UserRepository.get_or_create_user(
            email,
        )

        updated = await ExpenseRepository.update(
            user_id=user_id,
            expense_id=expense_id,
            expense_date=data.date,
            amount=data.amount,
            category=category,
            subcategory=subcategory,
            note=data.note.strip(),
            is_borrowed=is_borrowed,
            is_settled=data.is_settled,
        )

        if not updated:

            return {
                "status": "error",
                "message": "Expense not found.",
            }

        return {
            "status": "ok",
            "message": "Expense updated successfully.",
        }

    @staticmethod
    async def recent(
        email: str,
        limit: int = 10,
    ) -> dict:

        user_id = await UserRepository.get_or_create_user(
            email,
        )

        expenses = await ExpenseRepository.recent(
            user_id,
            limit,
        )

        return {
            "status": "ok",
            "expenses": expenses,
        }

    @staticmethod
    async def settle_expense(
        email: str,
        expense_id: int,
        is_settled: bool = True,
    ) -> dict:

        user_id = await UserRepository.get_or_create_user(
            email,
        )

        updated = await ExpenseRepository.settle(
            user_id,
            expense_id,
            is_settled,
        )

        if not updated:
            return {
                "status": "error",
                "message": "Borrowed expense not found.",
            }

        status_text = "settled" if is_settled else "unsettled"
        return {
            "status": "ok",
            "message": f"Expense marked as {status_text} successfully.",
        }