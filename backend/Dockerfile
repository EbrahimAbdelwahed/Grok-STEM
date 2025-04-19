# backend/Dockerfile

# 1. Use an official Python runtime as a parent image
# Using python:3.11-slim for a smaller image size
FROM python:3.11-slim

# 2. Set environment variables
# Prevents Python from writing pyc files to disc (optional) 
ENV PYTHONDONTWRITEBYTECODE=1
# Ensures Python output is sent straight to the terminal without buffering
ENV PYTHONUNBUFFERED=1

# 3. Set the working directory in the container
WORKDIR /app

# 4. Install system dependencies (if any are needed later, add them here)
# Example: RUN apt-get update && apt-get install -y --no-install-recommends some-package && rm -rf /var/lib/apt/lists/*

# 5. Install Python dependencies
# Copy only the requirements file first to leverage Docker cache
COPY requirements.txt /app/requirements.txt
# Upgrade pip and install packages
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# 6. Copy the rest of the application code into the container
# This happens *after* installing dependencies, so changes to code
# don't invalidate the dependency cache layer unless requirements.txt changes.
COPY . .

# 7. Expose the port the app runs on (matches the command in docker-compose.yml)
EXPOSE 8000

# 8. Define the default command to run the application (can be overridden by docker-compose)
# This is a fallback if docker-compose doesn't specify a command
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]