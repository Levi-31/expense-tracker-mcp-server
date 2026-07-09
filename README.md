# 💰 Expense Tracker MCP Server

A production-ready **Async Expense Tracker MCP Server** built using **FastMCP**, **PostgreSQL (Neon)** and **Python**.

The server exposes expense management capabilities as MCP tools that can be consumed by ChatGPT or any MCP-compatible client.

---

# Features

- ✅ Add expenses
- ✅ List expenses within a date range
- ✅ Update existing expenses
- ✅ Delete expenses
- ✅ Set monthly budget
- ✅ Set monthly credit/income
- ✅ View monthly finance
- ✅ Dashboard style summary
- ✅ Category-wise analytics
- ✅ Recent expenses
- ✅ Async PostgreSQL connection pooling
- ✅ Fully asynchronous architecture
- ✅ Repository-Service design pattern
- ✅ Production-ready codebase

---

# Tech Stack

- Python 3.11+
- FastMCP
- PostgreSQL (Neon)
- psycopg3
- psycopg Async Connection Pool
- Pydantic
- uv

---

# Project Structure

```
expense-tracker/
│
├── app/
│   ├── config.py
│   ├── database.py
│   ├── schema.py
│   ├── models.py
│   ├── resources.py
│   │
│   ├── repositories/
│   │      expense_repository.py
│   │      finance_repository.py
│   │
│   └── services/
│          expense_service.py
│          finance_service.py
│          summary_service.py
│
├── categories.json
├── server.py
├── pyproject.toml
├── uv.lock
└── README.md
```

---

# Architecture

```
                ChatGPT

                    │

                    ▼

             FastMCP HTTP Server

                    │

            Async MCP Tools

                    │

            Service Layer

                    │

          Repository Layer

                    │

      Async PostgreSQL Pool

                    │

              Neon Database
```

The project follows a layered architecture:

- MCP Layer
- Service Layer
- Repository Layer
- PostgreSQL

Each layer has a single responsibility.

---

# Database Schema

## expenses

| Column | Type |
|---------|------|
| id | SERIAL PRIMARY KEY |
| date | DATE |
| amount | NUMERIC(12,2) |
| category | TEXT |
| subcategory | TEXT |
| note | TEXT |

---

## monthly_finance

| Column | Type |
|---------|------|
| month | DATE |
| budget | NUMERIC(12,2) |
| credit | NUMERIC(12,2) |

The month is stored as the first day of the month.

Example:

```
2026-07-01
```

---

# Installation

Clone the repository

```bash
git clone <repository-url>

cd expense-tracker
```

Install dependencies

```bash
uv sync
```

---

# Environment Variables

Create a `.env`

```
DATABASE_URL=postgresql://username:password@host/database?sslmode=require
```

Example

```
DATABASE_URL=postgresql://neondb_owner:********@ep-example.us-east-1.aws.neon.tech/neondb?sslmode=require
```

---

# Running Locally

```
uv run python server.py
```

The server starts on

```
http://localhost:8000
```

---

# MCP Tools

## add_expense

Adds a new expense.

Arguments

```
date
amount
category
subcategory
note
```

Example

```json
{
  "date":"2026-07-09",
  "amount":250,
  "category":"Food",
  "subcategory":"Lunch",
  "note":"Office Lunch"
}
```

---

## list_expenses

Lists expenses between two dates.

Arguments

```
start_date

end_date
```

---

## update_expense

Updates an existing expense.

Arguments

```
expense_id

date

amount

category

subcategory

note
```

---

## delete_expense

Deletes an expense.

Arguments

```
expense_id
```

---

## recent_expenses

Returns the latest expenses.

Arguments

```
limit
```

Default

```
10
```

---

## set_monthly_budget

Sets the monthly budget.

Arguments

```
month

budget
```

Example

```
month = 2026-07

budget = 50000
```

---

## set_monthly_credit

Sets the available monthly credit.

Arguments

```
month

credit
```

---

## get_monthly_finance

Returns

```
budget

credit
```

for a month.

---

## summarize

Returns a complete dashboard.

Arguments

```
start_date

end_date
```

Returns

```
Budget

Credit

Remaining Budget

Remaining Credit

Transactions

Average Transaction

Average Daily Spend

Largest Category

Category Wise Summary

Budget Utilization

Overspend Amount
```

Example

```json
{
  "status":"ok",
  "month":"2026-07",
  "budget":50000,
  "credit":70000,
  "total_expense":23500,
  "remaining_budget":26500,
  "remaining_credit":46500,
  "budget_used_percent":47,
  "transactions":38,
  "largest_category":"Food",
  "category_summary":[]
}
```

---

# Resources

The server exposes

```
expense://categories
```

which returns

```
categories.json
```

This allows ChatGPT to dynamically discover available categories.

---

# Async Design

The application is fully asynchronous.

Every database call uses

```
async/await
```

along with

```
AsyncConnectionPool
```

Benefits

- Connection reuse
- Better throughput
- Lower latency
- Concurrent query execution
- Non-blocking I/O

---

# Design Patterns Used

- Repository Pattern
- Service Layer Pattern
- Connection Pooling
- Dependency Separation
- Pydantic Validation

---

# PostgreSQL

Money values use

```
NUMERIC(12,2)
```

instead of floating point values.

This avoids rounding errors.

---

# Why PostgreSQL instead of SQLite?

SQLite is perfect for local applications but unsuitable for cloud deployment because:

- Read-only filesystem
- No concurrent writers
- Ephemeral storage

Neon PostgreSQL provides

- Persistent storage
- Managed backups
- SSL
- High availability
- Async support

---

# Deployment

Deploy on

- FastMCP Cloud
- Docker
- Railway
- Render
- Fly.io
- Any VPS

The server uses HTTP transport.

```
mcp.run(
    transport="http",
    host="0.0.0.0",
    port=8000,
)
```

---

# Development

Install new dependency

```
uv add <package>
```

Update lock file

```
uv lock
```

Run

```
uv run python server.py
```

---

# Future Improvements

- Authentication
- Multi-user support
- Expense search
- CSV Import
- CSV Export
- Recurring expenses
- Monthly reports
- Charts
- AI-powered spending insights
- Budget recommendations

---