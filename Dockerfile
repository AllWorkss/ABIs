FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc g++ libpq-dev curl git \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for Docker layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Download NLTK data needed by textblob
RUN python -c "import nltk; nltk.download('punkt'); nltk.download('averaged_perceptron_tagger')" || true

# Copy application code
COPY . .

# Railway sets PORT automatically
ENV PORT=7860
EXPOSE 7860

# Start command
CMD ["python", "app.py"]
