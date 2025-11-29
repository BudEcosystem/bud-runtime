FROM python:3.11.0

WORKDIR /app
COPY . .
# COPY alembic.ini /app/
# COPY alembic /app/alembic
# COPY requirements.txt /app/


RUN pip install --upgrade pip
RUN pip install -r ./requirements.txt
# RUN pip install .

COPY entrypoint_mcpgateway_api_token.sh /usr/bin/
RUN chmod +x /usr/bin/entrypoint_mcpgateway_api_token.sh
RUN apt update
RUN apt install -y curl jq

ENTRYPOINT ["entrypoint_mcpgateway_api_token.sh"]
CMD ["sh", "-c", "alembic -c ./alembic.ini upgrade head && uvicorn budprompt.main:app --host 0.0.0.0 --port 3015"]
