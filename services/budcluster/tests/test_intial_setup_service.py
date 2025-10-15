import sys
import os
import pytest
from unittest.mock import patch, MagicMock
from uuid import UUID

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


from budcluster.commons.constants import ClusterPlatformEnum
from budcluster.cluster_ops.kubernetes import KubernetesHandler

# Test constants
TEST_CLUSTER_ID = UUID("12345678-1234-5678-1234-567812345678")

@pytest.mark.asyncio
async def test_initial_setup():

    os.environ['ANSIBLE_PYTHON_INTERPRETER'] = '/Users/rahulvramesh/bud-v2/bud-serve-cluster/.venv/bin/python'  # Use the path from step 1
    # Test data
    kubeconfig = {
        "clusters": [
            {
                "cluster": {
                    "certificate-authority-data": "LS0tLS1CRUdJTiBDRVJUSUZJQ0FURS0tLS0tCk1JSUJkekNDQVIyZ0F3SUJBZ0lCQURBS0JnZ3Foa2pPUFFRREFqQWpNU0V3SHdZRFZRUUREQmhyTTNNdGMyVnkKZG1WeUxXTmhRREUzTXpReE5qazBPVFF3SGhjTk1qUXhNakUwTURrME5EVTBXaGNOTXpReE1qRXlNRGswTkRVMApXakFqTVNFd0h3WURWUVFEREJock0zTXRjMlZ5ZG1WeUxXTmhRREUzTXpReE5qazBPVFF3V1RBVEJnY3Foa2pPClBRSUJCZ2dxaGtqT1BRTUJCd05DQUFUdXB5S1NyZXJLaUJLR0RCc013bUNNS1RWY1R0MGVXOXJkZCtzUjlBV20KVTZTMzdJcnFSL3VmZVFBOTFJRkNuQWFKVFl4UE5iVXVjbjNkSldzTmphaTJvMEl3UURBT0JnTlZIUThCQWY4RQpCQU1DQXFRd0R3WURWUjBUQVFIL0JBVXdBd0VCL3pBZEJnTlZIUTRFRmdRVUpLbHVVcWpXemxHQVFsT0R5TllNCmtJYWlHODR3Q2dZSUtvWkl6ajBFQXdJRFNBQXdSUUlnTWtFRkRDWUVTVmtxOG9CQk1HakxDZlpsck51VEZSTVoKNFVFbDlndlhBYThDSVFDVDFpdklSWFUxN0EwTGJiSjFMeWxWcXlVRkJlazNzTStNMkFtNVJ5NEsyQT09Ci0tLS0tRU5EIENFUlRJRklDQVRFLS0tLS0K",
                    "server": "https://127.0.0.1:6444"
                },
                "name": "default"
            }
        ],
        "contexts": [
            {
                "context": {
                    "cluster": "default",
                    "user": "default"
                },
                "name": "default"
            }
        ],
        "current-context": "default",
        "kind": "Config",
        "preferences": {},
        "users": [
            {
                "name": "default",
                "user": {
                    "client-certificate-data": "LS0tLS1CRUdJTiBDRVJUSUZJQ0FURS0tLS0tCk1JSUJrVENDQVRlZ0F3SUJBZ0lJUmRlR0tZV2NHV0V3Q2dZSUtvWkl6ajBFQXdJd0l6RWhNQjhHQTFVRUF3d1kKYXpOekxXTnNhV1Z1ZEMxallVQXhOek0wTVRZNU5EazBNQjRYRFRJME1USXhOREE1TkRRMU5Gb1hEVEkxTVRJeApOREE1TkRRMU5Gb3dNREVYTUJVR0ExVUVDaE1PYzNsemRHVnRPbTFoYzNSbGNuTXhGVEFUQmdOVkJBTVRESE41CmMzUmxiVHBoWkcxcGJqQlpNQk1HQnlxR1NNNDlBZ0VHQ0NxR1NNNDlBd0VIQTBJQUJDcEg0cGRkZ0R6b29lTisKbVIyZXYwU3NLRzhkT2x6SGlZa3dYaXZta2IwM1RQQkx6QmJzamE0RFJjZzdJeSs0R2JVYzJTM2FBblV5NDFtRApEQnVPMk1xalNEQkdNQTRHQTFVZER3RUIvd1FFQXdJRm9EQVRCZ05WSFNVRUREQUtCZ2dyQmdFRkJRY0RBakFmCkJnTlZIU01FR0RBV2dCUi9CTWFQa0RPSC8zMGd3dUU5RWtlcmNxYzkzVEFLQmdncWhrak9QUVFEQWdOSUFEQkYKQWlFQTNXVjhMWTd5VENDN3NmaXV4NUM0WDlsWW5hU0tmc3MyRHl3SmtLZVd5TGtDSUhMZExxS0JjUTNXd1ZJZwprQU1VcU5YdExEWUU4REZpWE4ycWNHT2V0V3BOCi0tLS0tRU5EIENFUlRJRklDQVRFLS0tLS0KLS0tLS1CRUdJTiBDRVJUSUZJQ0FURS0tLS0tCk1JSUJkekNDQVIyZ0F3SUJBZ0lCQURBS0JnZ3Foa2pPUFFRREFqQWpNU0V3SHdZRFZRUUREQmhyTTNNdFkyeHAKWlc1MExXTmhRREUzTXpReE5qazBPVFF3SGhjTk1qUXhNakUwTURrME5EVTBXaGNOTXpReE1qRXlNRGswTkRVMApXakFqTVNFd0h3WURWUVFEREJock0zTXRZMnhwWlc1MExXTmhRREUzTXpReE5qazBPVFF3V1RBVEJnY3Foa2pPClBRSUJCZ2dxaGtqT1BRTUJCd05DQUFSdmZENHpsWnhVYkxvUC83ZmxWTjB2NjMrTDg4cTRKWUpQWU96RmpYSmQKQlpaQzNIRDU5N0NYVUNJSzBKdlQ5NUNDUE9NWFdDZWNTMDhNNTJ2aEtYR05vMEl3UURBT0JnTlZIUThCQWY4RQpCQU1DQXFRd0R3WURWUjBUQVFIL0JBVXdBd0VCL3pBZEJnTlZIUTRFRmdRVWZ3VEdqNUF6aC85OUlNTGhQUkpICnEzS25QZDB3Q2dZSUtvWkl6ajBFQXdJRFNBQXdSUUloQUs0UmlrYnpsdkZOeWo2d0xtZVFzQXc3cWgrV3h0QU8KT3d1Ly8rV1RxTkV1QWlBa2F2OU55cm5BTXFRL2F4U3QydENPeFhPSW9EaEpGdUZyZGNiaFJvSFhXUT09Ci0tLS0tRU5EIENFUlRJRklDQVRFLS0tLS0K",
                    "client-key-data": "LS0tLS1CRUdJTiBFQyBQUklWQVRFIEtFWS0tLS0tCk1IY0NBUUVFSURtWFNlbVBabDQ5Y3JFTllhdVJmL1NnT2s2RGl5aFVtNzAzTnNQdGo0OEFvQW9HQ0NxR1NNNDkKQXdFSG9VUURRZ0FFS2tmaWwxMkFQT2loNDM2WkhaNi9SS3dvYngwNlhNZUppVEJlSythUnZUZE04RXZNRnV5TgpyZ05GeURzakw3Z1p0UnpaTGRvQ2RUTGpXWU1NRzQ3WXlnPT0KLS0tLS1FTkQgRUMgUFJJVkFURSBLRVktLS0tLQo="
                }
            }
        ]
    }
    cluster_id = TEST_CLUSTER_ID
    platform = ClusterPlatformEnum.KUBERNETES

    handler = KubernetesHandler(config=kubeconfig)

    # Call the initial_setup method
    status = handler.initial_setup(cluster_id)

    print(status)

    # Mock the KubernetesHandler dependencies
    # with patch('kubernetes.config.load_kube_config_from_dict') as mock_kube_config, \
    #      patch('kubernetes.client.CoreV1Api') as mock_core_v1_api, \
    #      patch('budcluster.cluster_ops.ansible.AnsibleExecutor._setup_ansible_logger', return_value=MagicMock()):

    #     # Instantiate the KubernetesHandler
    #     handler = KubernetesHandler(config=config_dict)

    #     # Mock the AnsibleExecutor's run_playbook method
    #     handler.ansible_executor.run_playbook = MagicMock(return_value={"status": "successful", "events": []})

    #     # Execute the initial_setup method
    #     status = handler.initial_setup(cluster_id)

    #     # Assertions
    #     assert status == "successful"
    #     mock_kube_config.assert_called_once()
    #     handler.ansible_executor.run_playbook.assert_called_once_with(
    #         playbook="DEPLOY_NFD",  # Updated to use NFD
    #         extra_vars={
    #             "kubeconfig_content": config_dict,
    #             "platform": handler.platform,
    #             "prometheus_url": handler.config + "/api/v1/write",
    #             "prometheus_namespace": "bud-system",
    #             "cluster_name": str(cluster_id),
    #             "namespace": "bud-runtime",
    #             "enable_nfd": True,
    #         }
    #     )
