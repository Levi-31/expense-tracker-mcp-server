from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field


class UserCreate(BaseModel):

    email: str = Field(min_length=1, max_length=255)

    full_name: str = ""


class ExpenseCreate(BaseModel):

    date: date

    amount: Decimal = Field(gt=0)

    category: str

    subcategory: str = ""

    note: str = ""


class MonthlyBudget(BaseModel):

    month: date

    budget: Decimal = Field(ge=0)


class MonthlyCredit(BaseModel):

    month: date

    credit: Decimal = Field(ge=0)