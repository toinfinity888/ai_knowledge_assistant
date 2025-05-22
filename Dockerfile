FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .


RUN pip install --no-cache-dir -r requirements.txt --no-deps

RUN pip install --no-cache-dir torch==2.7.0+cpu -f https://download.pytorch.org/whl/torch_stable.html

COPY . .

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001", "--reload"]
    CMD ["sh", "-c", "gunicorn main:app --bind 0.0.0.0:8080"]