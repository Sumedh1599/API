# Use Python image
FROM python:3.10-slim-buster

# Set the working directory
WORKDIR /app

# Install system dependencies required by Playwright
RUN apt-get update && apt-get install -y \
    wget gnupg libnss3 libatk1.0 libcups2 libxkbcommon-x11-0 libgbm-dev \
    libasound2 libpangocairo-1.0-0 libpangoft2-1.0-0 fonts-liberation \
    libjpeg62-turbo libxcomposite1 libxrandr2 && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN playwright install

# Copy application code
COPY . .

# Expose the port
EXPOSE 8080

# Run the app
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
