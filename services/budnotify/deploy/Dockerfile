FROM python:3.11.0

RUN mkdir /app/
COPY .. /app/

WORKDIR /app
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r ./requirements.txt
