"""Seeder script to add data to database and dapr statestore."""

import asyncio
import json
import os
import sys
from typing import Any, Dict, List

import yaml
from pydantic import PostgresDsn


project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
print(project_root)
sys.path.insert(0, project_root)

from budmicroframe.shared.dapr_service import DaprServiceCrypto  # noqa: E402

from budcluster.cluster_ops import get_node_info  # noqa: E402
from budcluster.cluster_ops.crud import ClusterDataManager, ClusterNodeInfoDataManager  # noqa: E402
from budcluster.cluster_ops.models import Cluster as ClusterModel  # noqa: E402
from budcluster.cluster_ops.models import ClusterNodeInfo as ClusterNodeInfoModel  # noqa: E402
from budcluster.cluster_ops.schemas import ClusterCreate, ClusterNodeInfo  # noqa: E402
from budcluster.cluster_ops.services import ClusterOpsService  # noqa: E402
from budcluster.cluster_ops.utils import get_cluster_hostname, get_cluster_server_url  # noqa: E402
from budcluster.commons.constants import ClusterPlatformEnum, ClusterStatusEnum  # noqa: E402
from budcluster.commons.database import SessionLocal  # noqa: E402


def get_psql_url() -> PostgresDsn:
    """Get the psql url."""
    if os.getenv("PSQL_HOST") is None or os.getenv("PSQL_PORT") is None or os.getenv("PSQL_DB_NAME") is None:
        raise ValueError("PSQL_HOST, PSQL_PORT, and PSQL_DB_NAME must be set")
    return PostgresDsn.build(
        scheme="postgresql+psycopg",
        username=os.getenv("SECRETS_PSQL_USER"),
        password=os.getenv("SECRETS_PSQL_PASSWORD"),
        host=os.getenv("PSQL_HOST"),
        port=int(os.getenv("PSQL_PORT")),
        path=os.getenv("PSQL_DB_NAME", "budcluster"),
    ).__str__()


def read_config_file() -> Dict[str, Any]:
    """Read the config file."""
    filename = "test_cluster_config.yaml"
    if os.path.exists(filename):
        with open(filename, "r") as file:
            return yaml.safe_load(file)
    else:
        raise FileNotFoundError(f"{filename} file not found")


def add_data_to_cluster_table(name: str, ingress_url: str) -> ClusterModel:
    """Add data to cluster table."""
    config_dict = read_config_file()
    configuration_str = json.dumps(config_dict)
    with DaprServiceCrypto() as dapr_service:
        configuration_encrypted = dapr_service.encrypt_data(configuration_str)

    platform = ClusterPlatformEnum.KUBERNETES

    hostname = asyncio.run(get_cluster_hostname(config_dict, platform))
    server_url = asyncio.run(get_cluster_server_url(config_dict))

    with SessionLocal() as session:
        db_cluster = asyncio.run(
            ClusterDataManager(session).retrieve_cluster_by_fields(
                {"configuration": configuration_encrypted}, missing_ok=True
            )
        )

        if db_cluster:
            # delete data from statestore
            asyncio.run(ClusterOpsService.delete_node_info_from_statestore(db_cluster.id))
            asyncio.run(ClusterNodeInfoDataManager(session).delete_cluster_node_info_by_cluster_id(db_cluster.id))
            asyncio.run(ClusterDataManager(session).delete_cluster(db_cluster=db_cluster))

    cluster_data = ClusterCreate(
        platform=platform,
        configuration=configuration_encrypted,
        host=hostname,
        status=ClusterStatusEnum.AVAILABLE,
        enable_master_node=True,
        ingress_url=ingress_url,
        server_url=server_url,
    )
    cluster_model = ClusterModel(**cluster_data.model_dump())
    with SessionLocal() as session:
        db_cluster = asyncio.run(ClusterDataManager(session).create_cluster(cluster_model))
    return db_cluster


def add_data_to_cluster_node_info_table(db_cluster: ClusterModel, cluster_name: str) -> List[ClusterNodeInfoModel]:
    """Add data to cluster node info table."""
    cluster_id = db_cluster.id

    config_dict = db_cluster.config_file_dict
    node_info = asyncio.run(get_node_info(config_dict))
    node_objects = []
    for node in node_info:
        devices = json.loads(node.get("devices", "[]"))
        hardware_info = devices[0]["device_info"] if len(devices) > 0 else {}
        device_type = devices[0]["type"] if len(devices) > 0 else "cpu"
        node_objects.append(
            ClusterNodeInfo(
                cluster_id=cluster_id,
                name=node["node_name"],
                type=device_type,
                hardware_info=devices,
                status=node["node_status"],
                status_sync_at=node["timestamp"],
                threads_per_core=hardware_info.get("threads_per_core", 0),
                core_count=hardware_info.get("num_physical_cores", 0),
            )
        )
    # add node info to db
    with SessionLocal() as session:
        db_nodes = asyncio.run(ClusterNodeInfoDataManager(session).create_cluster_node_info(node_objects))

    nodes = asyncio.run(ClusterOpsService.transform_db_nodes(db_nodes))

    result = {
        "id": str(cluster_id),
        "name": cluster_name,
        "nodes": nodes,
    }

    return result


if __name__ == "__main__":
    """Main function to add data to db and statestore.

    Note: Cluster platform is hardcoded to kubernetes.
    `name` of the cluster is hardcoded to seeder-test-cluster.
    This `name` is used to identify the cluster in the database already exists or not.
    `ingress_url` added for given cluster config file.
    """
    cluster_name = "seeder-test-cluster"
    # Add cluster to db
    db_cluster = add_data_to_cluster_table(name=cluster_name, ingress_url="https://20.244.107.114:10001")
    # Add node info to db
    cluster_info = add_data_to_cluster_node_info_table(db_cluster, cluster_name)
    # Save node info to statestore
    asyncio.run(ClusterOpsService.update_node_info_in_statestore(json.dumps(cluster_info)))
