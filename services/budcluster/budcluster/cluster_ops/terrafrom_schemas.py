from typing import Dict, Optional

from pydantic import BaseModel


# =================== Base Models ===================
class TagsModel(BaseModel):
    """Base model for resource tags"""

    Environment: str
    Project: str
    Owner: str
    CostCenter: Optional[str] = None
    ManagedBy: str = "Bud"

    def to_dict(self) -> Dict[str, str]:
        return self.model_dump(exclude_none=True)


# class NetworkInterface(BaseModel):
#     """Base model for network interfaces"""
#     pass


# class NodePoolInterface(BaseModel):
#     """Base model for node pool configurations"""
#     pass


# class ClusterInterface(BaseModel):
#     """Base model for cluster configurations"""
#     cluster_name: str


# class CloudProviderModel(BaseModel):
#     """Base model for cloud provider configurations"""
#     resource_group_name: str
#     location: str
#     environment: str
#     tags: TagsModel


# Cloud Specific Model
class AzureConfig(BaseModel):
    """Azure specific configuration model"""

    # Credentails
    subscription_id: str
    tenant_id: str
    client_id: str
    client_secret: str

    # Cluster Details
    cluster_name: str
    cluster_location: Optional[str] = None
    resource_group_name: str

    tags: Optional[TagsModel] = None


class AWSConfig(BaseModel):
    """AWS specific configuration model"""

    # Credentails
    access_key: str
    secret_key: str
    region: str
    vpc_name: str
    cluster_name: str

    tags: Optional[TagsModel] = None
