# Use Python 3.12 for compatibility with numpy 1.23.0
FROM python:3.12-slim-bullseye

# Install system dependencies for pypotrace, Pillow, and other packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    libagg-dev \
    potrace \
    pkg-config \
    zlib1g-dev \
    python3-dev \
 && rm -rf /var/lib/apt/lists/*

# Set a working directory
WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy all project files
COPY . .

# Use Gunicorn to run the backend Flask app
CMD gunicorn backend:app --bind 0.0.0.0:$PORT

