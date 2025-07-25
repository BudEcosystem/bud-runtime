# BudServe Simulator


## Project Architecture

The project consists of several containers:

- **Redis**: Used for pub/sub and state store.
- **Dapr Containers**: Various services of the Dapr platform.
  
### Prerequisites

- Docker and Docker Compose installed.

### Steps to Setup

1. **Clone the Repository**:
    ```bash
    git clone https://github.com/BudEcosystem/bud-serve-budsim
    cd bud-serve-budsim
    ```
2. **Set environment variables**:
    ```bash
    cp .env.sample .env
    ```
3. **Start project**:
    
    Use the following command to bring up all the services, including Dapr:
    ```bash
    cd bud-serve-budsim

    ./deploy/start_dev.sh
    ```

## Running Tests

To run the tests, make sure the Dapr API token is available in the environment. You can execute the tests using:

```bash
pytest --dapr-http-port 3510 --dapr-api-token <YOUR_DAPR_API_TOKEN>
```