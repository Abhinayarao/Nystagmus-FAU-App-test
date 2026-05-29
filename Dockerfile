FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    libgl1-mesa-dri \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY python/requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend code
COPY python/ ./python/

# Expose port
EXPOSE 8080

# Run the backend
CMD ["uvicorn", "python.backend:app", "--host", "0.0.0.0", "--port", "8080"]