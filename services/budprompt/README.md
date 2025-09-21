# 🥷 BudPrompt


A full-featured platform for designing, testing, comparing, and deploying LLM prompts — including support for tools (MCPs), structured output, prompt versioning, analytics, and scaling.


### Steps to Setup Development environment

1.Clone the Repository:
```bash
git clone https://github.com/BudEcosystem/bud-serve-prompt
cd bud-serve-prompt
```
2.Set environment variables:
```bash
cp .env.sample .env
```
3.Start project:

Use the following command to bring up all the services, including Dapr:
```bash
cd bud-serve-prompt

./deploy/start_dev.sh
```


### Steps to Setup Production environment

1.Clone the Repository:
```bash
git clone https://github.com/BudEcosystem/bud-serve-prompt
cd bud-serve-prompt
```
2.Run Helm chart
```bash
helm install bud-serve-prompt ./deploy/helm -n bud-serve-prompt --create-namespace
```

### Steps to run migrations

Execute in docker container

Generate alembic revision
```bash
alembic -c ./alembic.ini revision --autogenerate -m "message"
```

Apply migrations
```bash
alembic -c ./alembic.ini upgrade head
```
