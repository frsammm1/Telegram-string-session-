FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy bot file
COPY bot.py .

# Run the bot
CMD ["python", "-u", "bot.py"]
