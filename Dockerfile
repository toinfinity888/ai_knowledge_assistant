# ---- Stage 1: Builder ----
    FROM python:3.12-slim AS builder

    WORKDIR /install
    
    COPY requirements.txt .
    
    RUN pip install --upgrade pip && \
        pip install --no-cache-dir --prefix=/install/deps -r requirements.txt
    
    # ---- Stage 2: Final image ----
    FROM python:3.12-slim
    
    WORKDIR /app
    
    # Копируем только установленные библиотеки
    COPY --from=builder /install/deps /usr/local
    
    COPY . .
    
    EXPOSE 8080

    CMD ["gunicorn", "main:app", "--bind", "0.0.0.0:8080", "--workers", "1", "--threads", "1"]