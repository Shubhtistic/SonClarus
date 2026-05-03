# we use an lighweight linx os and python3.10
FROM python:3.11-slim


# install imp packages using apt-get
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    ffmpeg \ 
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# creates a folder called app
WORKDIR /sonclarus

# copy requirments file and download everything in it
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# copy all code
COPY ./app ./app
COPY ./alembic ./alembic
COPY alembic.ini .
RUN mkdir -p uploads
