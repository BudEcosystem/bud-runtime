FROM python:3.11.0

WORKDIR /app

COPY requirements.txt .

RUN pip install --upgrade pip
RUN pip install -r ./requirements.txt

COPY . .

RUN pip install .
