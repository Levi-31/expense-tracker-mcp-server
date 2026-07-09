from app.databases import get_connection


async def init_db():

    async with get_connection() as conn:

        async with conn.cursor() as cur:

            await cur.execute(
                """
                CREATE TABLE IF NOT EXISTS expenses(

                    id SERIAL PRIMARY KEY,

                    date DATE NOT NULL,

                    amount NUMERIC(12,2) NOT NULL,

                    category TEXT NOT NULL,

                    subcategory TEXT DEFAULT '',

                    note TEXT DEFAULT ''

                );
                """
            )

            await cur.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_expense_date
                ON expenses(date);
                """
            )

            await cur.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_expense_category
                ON expenses(category);
                """
            )

            await cur.execute(
                """
                CREATE TABLE IF NOT EXISTS monthly_finance(

                    month DATE PRIMARY KEY,

                    budget NUMERIC(12,2) DEFAULT 0,

                    credit NUMERIC(12,2) DEFAULT 0

                );
                """
            )

        await conn.commit()