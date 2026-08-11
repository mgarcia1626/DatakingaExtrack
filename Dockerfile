# Microsoft Playwright image - Chromium + all system deps pre-installed
FROM mcr.microsoft.com/playwright/python:v1.44.0-jammy

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright Chromium browser (binaries only - deps already in base image)
RUN playwright install chromium

# Copy application code
COPY . .

# Default command (overridden per service in render.yaml)
CMD ["streamlit", "run", "main_dashboard.py", "--server.port", "8501", "--server.address", "0.0.0.0"]
