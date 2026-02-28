# Use an official Python runtime as a parent image
FROM python:3.13-slim

# Set the working directory in the container
WORKDIR /app

# Install system dependencies (e.g., git for cloning)
RUN apt-get update && apt-get install -y git curl && rm -rf /var/lib/apt/lists/*

# Install uv for fast package management
# Use standard installer or pip if preferred, but Astral script is fine.
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.cargo/bin:$PATH"

# Copy the project files
COPY pyproject.toml .
COPY uv.lock .
COPY README.md .
COPY src ./src
COPY main.py .

# Install dependencies using uv
# Sync environments. Using --system to install into system python or create a venv.
# Docker usually prefers system python or a specific venv.
# uv sync creates a .venv. We can add it to path.
RUN uv sync
ENV PATH="/app/.venv/bin:$PATH"

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Run the auditor
CMD ["uv", "run", "main.py"]
