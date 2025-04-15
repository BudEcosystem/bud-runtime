import argparse
import os
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa


def generate_key_pair(directory: str, password: str) -> None:
    # Convert the private key password to bytes
    password = password.encode("utf-8")

    # Set the key size for RSA key pair generation
    key_size = 2048  # Should be at least 2048

    # Generate the RSA private key
    print("* Generating RSA key pair...")
    private_key = rsa.generate_private_key(
        public_exponent=65537,  # Do not change
        key_size=key_size,
    )

    # Serialize the private key to PEM format with encryption
    private_pem_bytes = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,  # PEM Format is specified
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.BestAvailableEncryption(
            password
        ),  # Encrypt with password
    )
    print("* Encrypted private key with password:", password.decode("utf-8"))

    # Write the private key to a PEM file
    private_pem_path = Path(os.path.join(directory, "private_key.pem"))
    private_pem_path.write_bytes(private_pem_bytes)
    print("* Created RSA private key in", private_pem_path)

    # Get the corresponding public key
    public_key = private_key.public_key()

    # Serialize the public key to PEM format
    public_pem_bytes = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )

    # Write the public key to a PEM file
    public_pem_path = Path(os.path.join(directory, "public_key.pem"))
    public_pem_path.write_bytes(public_pem_bytes)
    print("* Created RSA public key in", public_pem_path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate RSA key pair")
    parser.add_argument(
        "--directory",
        type=str,
        default=os.getcwd(),
        help="Directory to save the key pair files (default: current working directory)",
    )
    parser.add_argument(
        "--password",
        type=str,
        default="qwerty12345",
        help="Password to encrypt the private key (default: 'qwerty12345')",
    )
    args = parser.parse_args()

    generate_key_pair(args.directory, args.password)
