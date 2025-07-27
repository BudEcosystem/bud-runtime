FROM python:3.11.0

WORKDIR /app

COPY . .
# RUN chmod +x ./startup.sh

RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r ./requirements.txt
RUN pip install .
