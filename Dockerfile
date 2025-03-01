# Use an official Python base image (Debian-based) with Python 3.11
FROM python:3.11-slim-bullseye

# Install system dependencies for pypotrace
RUN apt-get update && apt-get install -y --no-install-recommends \
    libagg-dev \
    potrace \
 && rm -rf /var/lib/apt/lists/*

# Set a working directory
WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy your application code
COPY . .

# Tell Koyeb how to run your app (e.g., using Gunicorn)
CMD gunicorn backend:app --bind 0.0.0.0:$PORT

