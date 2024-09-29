# BudServeNotify

![](https://badgen.net/badge/PyGuard/verified/green)

This project is a FastAPI-based wrapper over the [Novu](https://v0.x-docs.novu.co/getting-started/introduction) notification platform, integrated with Dapr for state management and pub/sub functionality. It follows the [pyguard](https://github.com/BudEcosystem/bud-microframe-pyguard) coding standards, which ensures high-quality, maintainable code.

## Project Architecture

The project consists of several containers:

- **Redis**: Used for pub/sub and state store.
- **MongoDB**: The database for Novu.
- **Novu Containers**: Various services of the Novu notification platform (excluding the web component for production).
- **Dapr Containers**: Various services of the Dapr platform.
  
### Prerequisites

- Docker and Docker Compose installed.

### Steps to Setup

1. **Clone the Repository**:
    ```bash
    git clone https://github.com/BudEcosystem/bud-serve-notify
    cd bud-serve-notify
    ```
2. **Setup Secrets**:
    ```bash
    cp sample.secrets.json secrets.json
    ```
3. **Set environment variables**:
    ```bash
    cd deploy
    cp example.env .env
    ```
4. **Start project**:
    
    Use the following command to bring up all the services, including Dapr:
    ```bash
    cd bud-serve-notify

    ./deploy/start_dev.sh --app-name notify --redis-password <redis_password> --build
    ```
    **Note**
    - Use redis-password same as in secrets.json
    - While the project is starting up, note down the Dapr API token. This is necessary for running the tests with `pytest`.


## Running Tests

To run the tests, make sure the Dapr API token is available in the environment. You can execute the tests using:

```bash
pytest --dapr-http-port 3510 --dapr-api-token <YOUR_DAPR_API_TOKEN>
```

## Frontend integration

To integrate the frontend with this project, you will need the NOVU_APP_ID. This ID must be available for the frontend to interact with the Novu platform. Ensure that this is exported as an environment variable during the deployment or after the initial setup.


## Reference

- Novu documentation: https://v0.x-docs.novu.co/api-reference/overview
- Novu Docker self host: https://docs.novu.co/community/deploy-with-docker

    ```bash
    # Get the code
    git clone --depth 1 https://github.com/novuhq/novu

    # Go to the docker community folder
    cd novu/docker/community

    # Copy the example env file
    cp .env.example .env

    # Start Novu
    docker-compose -f docker-compose.yml up
    ```
