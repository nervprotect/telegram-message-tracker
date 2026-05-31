FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY bot.py .

# state.json пишется в DATA_DIR. На Railway примонтируй Volume и задай DATA_DIR=/data,
# иначе настройки (кто подключён, /check, исключения) теряются при перезапуске.
CMD ["python", "bot.py"]
