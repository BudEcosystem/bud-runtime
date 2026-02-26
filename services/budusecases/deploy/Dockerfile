FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
# git is required to install budmicroframe from GitHub
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install budmicroframe first (from GitHub)
RUN pip install --no-cache-dir git+https://github.com/BudEcosystem/bud-microframe.git

# Copy and install requirements
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY pyproject.toml README.md alembic.ini ./
COPY budusecases/ budusecases/
COPY alembic/ alembic/
COPY templates/ templates/

# Expose port
EXPOSE 9084

# Run the application
CMD ["uvicorn", "budusecases.main:app", "--host", "0.0.0.0", "--port", "9084"]
