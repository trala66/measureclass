# Use a base image for Python that works well on Cloud Run
FROM python:3.12-slim

# Set the working directory
WORKDIR /usr/src/app

# Install necessary dependencies for psycopg2
# The libpq-dev package is critical for PostgreSQL client libraries
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    libpq-dev \
    gcc && \
    rm -rf /var/lib/apt/lists/*

# Copy your application files into the container
COPY . .

# Install your Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Gunicorn is used as the production web server
CMD ["gunicorn", "--bind", "0.0.0.0:$PORT", "app:app"]