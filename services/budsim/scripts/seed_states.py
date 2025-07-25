import asyncio
import json
import os

from dapr.clients import DaprClient
from dapr.clients.grpc._state import Concurrency, Consistency, StateOptions
from dapr.conf import settings as dapr_settings
from dotenv import load_dotenv


load_dotenv()


async def seed_cluster_info(key: str, seed_file_path: str, statestore_name: str) -> None:
    """Seed the cluster information into the state store.

    This function reads the cluster state from a specified JSON file
    and saves it to the state store using the provided key.

    Args:
        key (str): The key under which the cluster information will be stored in the state store.
        seed_file_path (str): The file path to the JSON file containing the cluster state data.

    Raises:
        FileNotFoundError: If the specified state_file_path does not exist.
        json.JSONDecodeError: If the JSON file is not properly formatted.
    """
    with open(seed_file_path, "r") as f:
        state = json.load(f)

    with DaprClient() as dapr_client:
        resp = dapr_client.get_state(store_name=statestore_name, key=key)
        etag = resp.etag

        state_options = StateOptions(
            concurrency=Concurrency.first_write,
            consistency=Consistency.strong,
        )
        state_metadata = {"contentType": "application/json"}
        dapr_client.save_state(statestore_name, key, json.dumps(state), etag, state_options, state_metadata)


if __name__ == "__main__":
    if os.getenv("DAPR_HTTP_PORT"):
        dapr_settings.DAPR_HTTP_PORT = int(os.getenv("DAPR_HTTP_PORT"))
    if os.getenv("DAPR_GRPC_PORT"):
        dapr_settings.DAPR_GRPC_PORT = int(os.getenv("DAPR_GRPC_PORT"))
    if os.getenv("DAPR_API_TOKEN"):
        dapr_settings.DAPR_API_TOKEN = os.getenv("DAPR_API_TOKEN")

    dapr_settings.DAPR_API_METHOD_INVOCATION_PROTOCOL = "grpc"

    state_key = "cluster_info"
    seed_file_path = "examples/cluster_info.json"
    statestore_name = "statestore"

    asyncio.run(seed_cluster_info(state_key, seed_file_path, statestore_name))
