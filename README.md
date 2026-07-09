# 💰 Multi-User Expense Tracker MCP Server

A production-ready **Async Multi-User Expense Tracker MCP Server** built using **FastMCP**, **PostgreSQL (Neon)**, and **Python**.

This server is designed to support multiple users, isolating budgets, expenses, and monthly finance per user via their email address (auto-creating users dynamically on first use). It validates categories and subcategories dynamically using a localized configuration file, and isolates credit card self-usage from borrowed/lent expenses.

---

## 🚀 Key Features

### 👤 1. Zero-Config Multi-Tenant Isolation
- **Dynamic Onboarding**: No complex sign-up flows, passwords, or authentication overhead. The first time a user's email address is supplied in a tool call, a new user account is generated automatically.
- **Strict Data Isolation**: Every database query is restricted using `WHERE user_id = %s`. It is impossible for a user to view, edit, or delete another user's financial details.
- **Race-Condition Free**: Uses atomic `INSERT ... ON CONFLICT DO NOTHING` SQL followed by a SELECT query inside transactions to prevent duplicate user creation under high concurrent loads.

### 🏷️ 2. Dynamic Category & Subcategory Validation
- **Local Rules Engine**: Uses [category.json](file:///Users/sarthakshukla/Desktop/MCP/category.json) as the source of truth for allowed expense classifications.
- **Smart Normalization**: Automatically normalizes input casing, strips trailing/leading whitespaces, and converts spaces to underscores (e.g., inputting `"Food"` and `"Dining Out"` normalizes cleanly to `"food"` and `"dining_out"`).
- **Tool Discovery**: Exposes an MCP resource `expense://categories` containing the JSON config. This lets AI clients query and inspect valid classifications before calling tools.

### 💳 3. Borrowed Expense Isolation (Credit Card & Cash)
- **Separate Summaries**: Expenses flagged as borrowed are excluded from the user's monthly budget, personal spend, and average transaction stats.
- **Auto-Detection Rules**: The system automatically detects a borrowed expense if:
  1. The category is `"credit_card_usage"` and the subcategory is `"borrowed_to_friend"`.
  2. The note contains keywords like `"borrowed to friend"`, `"borrowed to a friend"`, or `"lent to"` (case-insensitive).
- **Virtual Categorization**: During monthly summary generations, all borrowed expenses are grouped and returned under a separate virtual category called `"borrowed"`, allowing clean data visualization.

---

## 🛠️ Tech Stack

- **Python 3.11+**
- **FastMCP**: Modern tool-first MCP server framework.
- **PostgreSQL (Neon-compatible)**: High-performance relational database.
- **psycopg3**: Modern, type-safe async driver for PostgreSQL.
- **psycopg-pool**: Connection pooler designed for high concurrent throughput.
- **Pydantic**: Robust runtime model typing and constraint validation.
- **uv**: Next-generation Python package management.

---

## 📁 Project Structure

```
expense-tracker/
│
├── app/
│   ├── config.py         # Loads database settings & pool sizing from environment
│   ├── databases.py      # Configures & lifecycle-manages psycopg connection pools
│   ├── schema.py         # Defines table queries, keys, indexes, and cascades
│   ├── models.py         # Contains Pydantic models for validation and type-hints
│   ├── resources.py      # Implements category loading and validation/normalization
│   │
│   ├── repository/       # Database query operations (zero business logic)
│   │      expense_repository.py
│   │      finance_repository.py
│   │      user_repository.py
│   │
│   └── services/         # Orchestrates business logic, validations, & orchestrates transactions
│          expense_service.py
│          finance_service.py
│          summary_service.py
│
├── category.json         # Source of truth for categories & subcategories
├── main.py               # Instantiates FastMCP, sets tool endpoints, & binds lifespan
├── pyproject.toml        # Declares project dependencies & tool mappings
├── uv.lock               # Deterministic dependency resolution lockfile
└── README.md             # Project documentation
```

---

## 📊 Database Schema Details

### 1. `users`
Represents the primary tenant identification.
```sql
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email TEXT UNIQUE NOT NULL,
    full_name TEXT DEFAULT '',
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

### 2. `expenses`
Stores transaction items linked to users.
```sql
CREATE TABLE expenses (
    id SERIAL PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    date DATE NOT NULL,
    amount NUMERIC(12,2) NOT NULL,
    category TEXT NOT NULL,
    subcategory TEXT DEFAULT '',
    note TEXT DEFAULT '',
    is_borrowed BOOLEAN DEFAULT FALSE
);

-- Optimize queries by user, dates, categories, and borrow status
CREATE INDEX idx_expense_user ON expenses(user_id);
CREATE INDEX idx_expense_user_date ON expenses(user_id, date);
CREATE INDEX idx_expense_user_category ON expenses(user_id, category);
CREATE INDEX idx_expense_user_borrowed ON expenses(user_id, is_borrowed);
```

### 3. `monthly_finance`
Stores budget limits and credit allocations.
```sql
CREATE TABLE monthly_finance (
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    month DATE NOT NULL,
    budget NUMERIC(12,2) DEFAULT 0,
    credit NUMERIC(12,2) DEFAULT 0,
    PRIMARY KEY (user_id, month)
);

CREATE INDEX idx_finance_user_month ON monthly_finance(user_id, month);
```

---

## ⚙️ Setup & Installation

### 1. Re-initialize Database (Breaking Schema Change)
If you had an old version of the database running, you must drop the old tables first:
```sql
DROP TABLE IF EXISTS expenses, monthly_finance, users CASCADE;
```

### 2. Setup Environment Variables
Create a `.env` file in the root directory:
```env
DATABASE_URL=postgresql://neondb_owner:********@ep-example.us-east-1.aws.neon.tech/neondb?sslmode=require
POOL_MIN_SIZE=2
POOL_MAX_SIZE=10
```

### 3. Synchronize Dependencies
Install python packages using `uv`:
```bash
uv sync
```

---

## 🚀 Running the Server

Start the server using `uv run`:
```bash
uv run fastmcp run main.py:mcp --transport http --host 0.0.0.0 --port 8000
```
This launches a SSE/HTTP server listening at `http://localhost:8000/mcp`.

---

## 🛠️ MCP Tools Reference

Every tool automatically takes `email: str` as the first parameter to identify the caller and scope operations.

### 1. `add_expense`
Adds a new expense.
- **Arguments**:
  - `email` (str): Email address of the user.
  - `date` (str): Date formatted as `"YYYY-MM-DD"`.
  - `amount` (float): Positive numeric value.
  - `category` (str): Key inside `category.json`.
  - `subcategory` (str): Sub-item matching category.
  - `note` (str): Optional description.
  - `is_borrowed` (bool, optional): Force flags the transaction as borrowed.

### 2. `list_expenses`
Fetch transactions for a given date range.
- **Arguments**:
  - `email` (str)
  - `start_date` (date)
  - `end_date` (date)

### 3. `update_expense`
Update a transaction (scopes updates to user owning the `expense_id`).
- **Arguments**:
  - `email` (str)
  - `expense_id` (int)
  - `date` (str)
  - `amount` (float)
  - `category` (str)
  - `subcategory` (str)
  - `note` (str)
  - `is_borrowed` (bool)

### 4. `delete_expense`
Permanently delete an expense.
- **Arguments**:
  - `email` (str)
  - `expense_id` (int)

### 5. `recent_expenses`
Get latest transactions.
- **Arguments**:
  - `email` (str)
  - `limit` (int, default=10)

### 6. `set_monthly_budget` / `set_monthly_credit`
Update financial targets for a specific month (composite PK handles conflicts).
- **Arguments**:
  - `email` (str)
  - `month` (str, format `"YYYY-MM"`)
  - `budget`/`credit` (float)

### 7. `summarize`
Generates a comprehensive financial overview of the month.
- **Arguments**:
  - `email` (str)
  - `start_date` (date)
  - `end_date` (date)
  - `category` (str, optional)

- **Example Output**:
  ```json
  {
    "status": "ok",
    "month": "2026-07",
    "budget": 50000.0,
    "credit": 70000.0,
    "total_expense": 23500.0,      // Excludes borrowed amounts
    "total_borrowed": 1500.0,      // Tracks borrowed separately
    "remaining_budget": 26500.0,
    "remaining_credit": 46500.0,
    "budget_used_percent": 47.0,
    "is_over_budget": false,
    "over_budget_amount": 0.0,
    "transactions": 38,
    "average_transaction": 618.42,
    "average_daily_spend": 758.06,
    "largest_category": "food",
    "largest_category_amount": 12000.0,
    "category_summary": [
      { "category": "food", "total_amount": 12000.0 },
      { "category": "transport", "total_amount": 8000.0 },
      { "category": "borrowed", "total_amount": 1500.0 }
    ]
  }
  ```

---

## 🤝 Integrating with Clients

### Claude Desktop Configuration
Add the following block to your `claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "expense-tracker": {
      "command": "uv",
      "args": [
        "--directory",
        "/absolute/path/to/expense-tracker",
        "run",
        "fastmcp",
        "run",
        "main.py:mcp"
      ]
    }
  }
}
```
*Note: Make sure to replace `/absolute/path/to/expense-tracker` with the actual path to your directory.*