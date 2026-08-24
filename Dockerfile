FROM python:3.12-slim

# Prevent Python from writing pyc files and keep stdout unbuffered
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install necessary system dependencies (curl for installing uv)
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

# Install uv (astral-sh) for fast dependency management
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:${PATH}"

# Copy only requirements first to leverage Docker layer caching
COPY pyproject.toml uv.lock* ./

# Install dependencies via uv (system-wide inside the container)
RUN uv sync --frozen --no-dev

# Copy the rest of the application codebase
COPY . .

# Expose the API port
EXPOSE 8000

# Default command to run the FastAPI application
CMD ["uv", "run", "uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
