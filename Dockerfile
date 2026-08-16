FROM python:3.11-slim

# Install system dependencies (FFmpeg, git, curl)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    git \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install Antigravity CLI (agy)
RUN curl -fsSL https://antigravity.google/install.sh | bash || true
ENV PATH="/root/.local/bin:${PATH}"

WORKDIR /app

# Install Python requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY . .

# Set execution permissions
RUN chmod +x start.sh service.sh bot.py

CMD ["python", "bot.py"]
