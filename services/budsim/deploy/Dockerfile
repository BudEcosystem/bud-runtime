FROM python:3.11.0

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir --upgrade pip
RUN pip install --no-cache-dir --prefer-binary -r ./requirements.txt

COPY . .

RUN pip install .
