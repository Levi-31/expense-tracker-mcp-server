# Use astral-sh/uv image for fast builds and smaller final size
FROM ghcr.io/astral-sh/uv:python3.11-alpine AS builder

# Set build directory
WORKDIR /app

# Enable bytecode compilation
ENV UV_COMPILE_BYTECODE=1

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install dependencies into a cacheable layer
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev

# Copy application code
COPY main.py category.json ./
COPY app ./app

# Final stage: Use a clean python base image to run the app
FROM python:3.11-alpine

WORKDIR /app

# Copy the environment and virtual env from the builder
COPY --from=builder /app /app
ENV PATH="/app/.venv/bin:$PATH"

# Expose HTTP port for FastMCP SSE transport
EXPOSE 8000

# Set environment variables
ENV PORT=8000
ENV PYTHONUNBUFFERED=1

# Run the FastMCP server
CMD ["python", "main.py"]
