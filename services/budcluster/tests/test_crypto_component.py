import json
import yaml
from budmicroframe.shared.dapr_service import DaprServiceCrypto


def test_crypto_component(config_str: str | None = None):
    dapr_service = DaprServiceCrypto()
    test_msg = config_str or "test message"
    encrypted_msg = dapr_service.encrypt_data(test_msg, key_wrap_algorithm="RSA")
    print(f"encrypted_msg: {encrypted_msg}")
    assert encrypted_msg is not None
    decrypted_msg = dapr_service.decrypt_data(encrypted_msg, key_wrap_algorithm="RSA")
    print(f"decrypted_msg: {decrypted_msg}")
    assert decrypted_msg == test_msg


if __name__ == "__main__":
    config_filepath = "test_cluster_config.yaml"
    with open(config_filepath, "r") as f:
        config = yaml.safe_load(f)

    config_str = json.dumps(config)
    config_str = None
    test_crypto_component(config_str)
