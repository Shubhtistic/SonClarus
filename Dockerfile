# we use an lighweight linx os and python3.10
FROM python:3.10-slim

# avoid __pycache__
ENV PYTHONDONTWRITEBYTECODE=1  

# Print logs
ENV PYTHONUNBUFFERED=1

# install imp packages using apt-get
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# creates a folder called app
WORKDIR /app

# copy requirments file and download everything in it
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# copy all code
COPY . .

RUN mkdir -p uploads
