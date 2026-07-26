FROM python:3.12-slim

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv for rapid Python dependency resolution
COPY --from=ghcr.io/astral-sh/uv:0.5.6 /uv /uvx /bin/

# Set working directory
WORKDIR /app

# Copy dependency files first
COPY pyproject.toml uv.lock ./

# Install dependencies using uv into the system python
RUN uv pip install --system --no-cache -r pyproject.toml

# Copy the rest of the application
COPY src/ src/

# Install the application itself
RUN uv pip install --system --no-cache .

# Create a non-root user for security (Sovereign 0-Trust)
RUN useradd -m -u 1000 -s /sbin/nologin tsuser && \
    chown -R tsuser:tsuser /app
USER tsuser
ENV HOME=/home/tsuser

# Set the entrypoint
ENTRYPOINT ["ts-proxy"]
