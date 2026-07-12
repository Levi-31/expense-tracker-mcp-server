from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from app.config import (
    DATABASE_URL,
    POOL_MIN_SIZE,
    POOL_MAX_SIZE,
)

async def check_connection(conn) -> None:
    """
    Verify the connection is alive before handing it out of the pool.
    This prevents 'terminating connection due to administrator command' errors.
    """
    await conn.execute("SELECT 1")


pool = AsyncConnectionPool(
    conninfo=DATABASE_URL,
    min_size=POOL_MIN_SIZE,
    max_size=POOL_MAX_SIZE,
    open=False,
    check=check_connection,
    kwargs={
        "row_factory": dict_row
    },
)


async def open_pool():
    await pool.open()


async def close_pool():
    await pool.close()


def get_connection():
    return pool.connection()