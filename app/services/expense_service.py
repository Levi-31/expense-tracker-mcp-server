from datetime import date

from app.models import ExpenseCreate
from app.repository.expense_repository import ExpenseRepository
from app.repository.user_repository import UserRepository


class ExpenseService:

    @staticmethod
    async def add_expense(
        email: str,
        data: ExpenseCreate,
    ) -> dict:

        user_id = await UserRepository.get_or_create_user(
            email,
        )

        expense_id = await ExpenseRepository.add(
            user_id=user_id,
            expense_date=data.date,
            amount=data.amount,
            category=data.category.strip(),
            subcategory=data.subcategory.strip(),
            note=data.note.strip(),
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

        user_id = await UserRepository.get_or_create_user(
            email,
        )

        updated = await ExpenseRepository.update(
            user_id,
            expense_id,
            data.date,
            data.amount,
            data.category,
            data.subcategory,
            data.note,
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