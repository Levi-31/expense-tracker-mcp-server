from app.databases import get_connection


async def init_db():

    async with get_connection() as conn:

        async with conn.cursor() as cur:

            # -------------------------------------------------
            # Users table
            # -------------------------------------------------

            await cur.execute(
                """
                CREATE TABLE IF NOT EXISTS users(

                    id UUID PRIMARY KEY
                        DEFAULT gen_random_uuid(),

                    email TEXT UNIQUE NOT NULL,

                    full_name TEXT DEFAULT '',

                    created_at TIMESTAMPTZ
                        DEFAULT NOW()

                );
                """
            )

            # -------------------------------------------------
            # Expenses table
            # -------------------------------------------------

            await cur.execute(
                """
                CREATE TABLE IF NOT EXISTS expenses(

                    id SERIAL PRIMARY KEY,

                    user_id UUID NOT NULL
                        REFERENCES users(id)
                        ON DELETE CASCADE,

                    date DATE NOT NULL,

                    amount NUMERIC(12,2) NOT NULL,

                    category TEXT NOT NULL,

                    subcategory TEXT DEFAULT '',

                    note TEXT DEFAULT '',

                    is_borrowed BOOLEAN DEFAULT FALSE,

                    is_settled BOOLEAN DEFAULT FALSE

                );
                """
            )

            # -------------------------------------------------
            # Expense indexes
            # -------------------------------------------------

            await cur.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_expense_user
                ON expenses(user_id);
                """
            )

            await cur.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_expense_user_date
                ON expenses(user_id, date);
                """
            )

            await cur.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_expense_user_category
                ON expenses(user_id, category);
                """
            )

            await cur.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_expense_user_borrowed
                ON expenses(user_id, is_borrowed);
                """
            )

            await cur.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_expense_user_settled
                ON expenses(user_id, is_borrowed, is_settled);
                """
            )

            # -------------------------------------------------
            # Monthly finance table
            # -------------------------------------------------

            await cur.execute(
                """
                CREATE TABLE IF NOT EXISTS monthly_finance(

                    user_id UUID NOT NULL
                        REFERENCES users(id)
                        ON DELETE CASCADE,

                    month DATE NOT NULL,

                    budget NUMERIC(12,2) DEFAULT 0,

                    credit NUMERIC(12,2) DEFAULT 0,

                    PRIMARY KEY (user_id, month)

                );
                """
            )

            # -------------------------------------------------
            # Monthly finance index
            # -------------------------------------------------

            await cur.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_finance_user_month
                ON monthly_finance(user_id, month);
                """
            )

            # -------------------------------------------------
            # User sessions table
            # -------------------------------------------------

            await cur.execute(
                """
                CREATE TABLE IF NOT EXISTS user_sessions(

                    session_id TEXT PRIMARY KEY,

                    user_id UUID NOT NULL
                        REFERENCES users(id)
                        ON DELETE CASCADE,

                    email TEXT NOT NULL,

                    updated_at TIMESTAMPTZ DEFAULT NOW()

                );
                """
            )

        await conn.commit()