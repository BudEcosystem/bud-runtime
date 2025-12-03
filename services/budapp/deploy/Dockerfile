FROM python:3.11.0

WORKDIR /app

COPY . .
# RUN chmod +x ./startup.sh

RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r ./requirements.txt
RUN pip install .

COPY entrypoint_mcpgateway_api_token.sh /usr/bin/
RUN chmod +x /usr/bin/entrypoint_mcpgateway_api_token.sh
RUN apt update
RUN apt install -y curl jq

ENTRYPOINT ["entrypoint_mcpgateway_api_token.sh"]
CMD ["sh", "-c", "alembic -c ./budapp/alembic.ini upgrade head && uvicorn budapp.main:app --host 0.0.0.0 --port 9082"]
