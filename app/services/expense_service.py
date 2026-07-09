from app.models import ExpenseCreate
from app.repository.expense_repository import ExpenseRepository


class ExpenseService:

    @staticmethod
    async def add_expense(data: ExpenseCreate):

        expense_id = await ExpenseRepository.add(
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
        start_date,
        end_date,
    ):

        expenses = await ExpenseRepository.list_between(
            start_date,
            end_date,
        )

        return {
            "status": "ok",
            "count": len(expenses),
            "expenses": expenses,
        }

    @staticmethod
    async def delete_expense(expense_id: int):

        deleted = await ExpenseRepository.delete(expense_id)

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
        expense_id: int,
        data: ExpenseCreate,
    ):

        updated = await ExpenseRepository.update(
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
    async def recent(limit: int = 10):

        expenses = await ExpenseRepository.recent(limit)

        return {
            "status": "ok",
            "expenses": expenses,
        }