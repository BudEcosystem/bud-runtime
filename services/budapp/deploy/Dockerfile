FROM python:3.11.0

WORKDIR /app

COPY requirements.txt ./requirements.txt
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r ./requirements.txt

COPY . .
# RUN chmod +x ./startup.sh

RUN pip install .

CMD ["sh", "-c", "alembic -c ./budapp/alembic.ini upgrade head && uvicorn budapp.main:app --host 0.0.0.0 --port 9082"]
