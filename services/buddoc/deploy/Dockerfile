FROM python:3.11.0

RUN python3 -m pip install uv

RUN uv pip install --system --upgrade pip

WORKDIR /app

COPY requirements.txt .
RUN uv pip install --system -r ./requirements.txt

COPY . .

RUN uv pip install --system .