import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from budcluster.terraform.aks_terraform import AzureAksManager
from budcluster.cluster_ops.terrafrom_schemas import AzureConfig, TagsModel

def main():
    # Config
    aks_config = AzureConfig(
        subscription_id = "e06b711a-bf90-4878-9d59-383f6112846c",
        tenant_id = "",
        client_id = "",
        client_secret = "",
        cluster_name = "bud-aks-test-eastus-cluster",
        cluster_location = "East US",
        resource_group_name = "bud-aks-test-eastus",
        tags = TagsModel(
                Environment="Production",
                Project="Bud Ecosystem Inc.",
                Owner="Bud Ecosystem Inc.",
            )
    )

    aksT = AzureAksManager(aks_config)

    # Lets call
    aksT.init()
    aksT.plan()
    aksT.apply()

    # Output
    outs = aksT.get_outputs()
    print("================")
    print(outs)
    print("================")

    # Destroy
    # aksT.destroy()
    # aksT.cleanup()

if __name__ == "__main__":
    main()
