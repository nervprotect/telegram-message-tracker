FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY bot.py .

# На Render (и вообще без REDIS_URL) состояние по умолчанию пишется в DATA_DIR —
# файловая система там эфемерная, всё теряется при каждом рестарте/редеплое.
# Задай REDIS_URL (например бесплатный Upstash Redis), тогда состояние переживает рестарты.
CMD ["python", "bot.py"]
