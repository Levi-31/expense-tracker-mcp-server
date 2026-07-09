import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if DATABASE_URL is None:
    raise RuntimeError(
        "DATABASE_URL environment variable not found."
    )

POOL_MIN_SIZE = int(
    os.getenv("POOL_MIN_SIZE", "2")
)

POOL_MAX_SIZE = int(
    os.getenv("POOL_MAX_SIZE", "10")
)

