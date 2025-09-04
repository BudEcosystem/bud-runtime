FROM python:3.11.0

WORKDIR /app
COPY . .
# COPY alembic.ini /app/
# COPY alembic /app/alembic
# COPY requirements.txt /app/


RUN pip install --upgrade pip
RUN pip install -r ./requirements.txt
# RUN pip install .