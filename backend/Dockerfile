# backend/Dockerfile

FROM python:3.11-slim

# 1. Prevent .pyc files and enable unbuffered logs
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# 2. Work inside /app/backend so it becomes a proper package directory
WORKDIR /app/backend

# 3. Install Python dependencies
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# 4. Copy all your backend code under /app/backend
COPY . .

# 5. Expose and launch
EXPOSE 8000
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
