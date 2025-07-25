# Bud Serve App
This is the application service for the Bud Runtime which handles user management, project management, cluster management etc

### Prerequisites

- Docker and Docker Compose installed.

### Steps to Setup

1. **Clone the Repository**:
    ```bash
    git clone https://github.com/BudEcosystem/bud-serve-app
    cd bud-serve-app
    ```
2. **Set environment variables**:
    ```bash
    cp .env.sample .env
    ```


3. **Start project**:

    Use the following command to bring up all the services, including Dapr:
    ```bash
    cd bud-serve-app

    ./deploy/start_dev.sh
    ```

## Running Tests

To run the tests, make sure the Dapr API token is available in the environment. You can execute the tests using:

```bash
pytest --dapr-http-port 3510 --dapr-api-token <YOUR_DAPR_API_TOKEN>
```

## Migrations

execute budapp container

``` bash
cd app/
alembic -c ./budapp/alembic.ini upgrade head
alembic -c ./budapp/alembic.ini revision --autogenerate -m "message"
```
