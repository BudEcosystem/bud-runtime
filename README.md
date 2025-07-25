# 🥷 BudPrompt


BudPrompt is a cloud service designed to complement and manage Bud inference runtimes deployed on customer infrastructure. It provides a central hub for compatibility validation of models and engine versions, acting as a registry and sync point for validated updates.


### Steps to Setup Development environment

1.Clone the Repository:
```bash
git clone https://github.com/BudEcosystem/bud-serve-budsim
cd bud-serve-budsim
```
2.Set environment variables:
```bash
cp .env.sample .env
```
3.Start project:

Use the following command to bring up all the services, including Dapr:
```bash
cd bud-serve-budsim

./deploy/start_dev.sh
```


### Steps to Setup Production environment

1.Clone the Repository:
```bash
git clone https://github.com/BudEcosystem/bud-serve-budsim
cd bud-serve-budsim
```
2.Run Helm chart
```bash
helm install bud-serve-budsim ./deploy/helm -n bud-serve-budsim --create-namespace
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