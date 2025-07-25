use crate::error::{Error, ErrorDetails};
use base64::{engine::general_purpose::STANDARD as BASE64, Engine};
use rsa::sha2::Sha256;
use rsa::{
    pkcs1::DecodeRsaPrivateKey, pkcs8::DecodePrivateKey, Oaep, Pkcs1v15Encrypt, RsaPrivateKey,
};
use secrecy::SecretString;
use std::env;

/// Try to parse a private key from PEM content, supporting both PKCS#1 and PKCS#8 formats
fn parse_private_key_from_pem(pem_content: &str, source: &str) -> Result<RsaPrivateKey, Error> {
    // First try PKCS#1 format
    if let Ok(key) = RsaPrivateKey::from_pkcs1_pem(pem_content) {
        tracing::debug!("Successfully loaded PKCS#1 private key from {}", source);
        return Ok(key);
    }

    // Try PKCS#8 format without password
    if let Ok(key) = RsaPrivateKey::from_pkcs8_pem(pem_content) {
        tracing::debug!(
            "Successfully loaded unencrypted PKCS#8 private key from {}",
            source
        );
        return Ok(key);
    }

    // If both fail, check if we have a password for encrypted PKCS#8
    if let Ok(password) = env::var("TENSORZERO_RSA_PRIVATE_KEY_PASSWORD") {
        tracing::debug!(
            "Attempting to decrypt private key from {} with password",
            source
        );

        // Try multiple approaches for encrypted keys

        // First, try using the rsa crate's built-in encrypted PEM support
        if let Ok(key) = RsaPrivateKey::from_pkcs8_encrypted_pem(pem_content, password.as_bytes()) {
            tracing::debug!(
                "Successfully loaded encrypted PKCS#8 private key using RSA crate from {}",
                source
            );
            return Ok(key);
        }

        // If that fails, try manual parsing
        use pkcs8::der::Decode;
        use pkcs8::EncryptedPrivateKeyInfo;

        // Check if it's an encrypted private key PEM
        if pem_content.contains("ENCRYPTED PRIVATE KEY") {
            // Parse the PEM manually
            let pem = pem::parse(pem_content).map_err(|e| {
                Error::new(ErrorDetails::Config {
                    message: format!("Failed to parse PEM from {source}: {e}"),
                })
            })?;

            // Try to parse as encrypted PKCS#8
            match EncryptedPrivateKeyInfo::from_der(pem.contents()) {
                Ok(enc_info) => {
                    // Log encryption scheme info for debugging
                    tracing::debug!(
                        "Encrypted private key uses encryption scheme: {:?}",
                        enc_info.encryption_algorithm
                    );

                    // Decrypt the private key
                    match enc_info.decrypt(password.as_bytes()) {
                        Ok(dec_doc) => {
                            // Parse the decrypted PKCS#8 data as RSA private key
                            match RsaPrivateKey::from_pkcs8_der(dec_doc.as_bytes()) {
                                Ok(key) => {
                                    tracing::debug!("Successfully decrypted and parsed RSA private key from {}", source);
                                    Ok(key)
                                },
                                Err(e) => Err(Error::new(ErrorDetails::Config {
                                    message: format!("Failed to parse decrypted RSA private key from {source}: {e}"),
                                }))
                            }
                        },
                        Err(e) => Err(Error::new(ErrorDetails::Config {
                            message: format!("Failed to decrypt RSA private key from {source} with password: {e}. Make sure the password is correct and the key uses a supported encryption algorithm (PBES2 with AES)"),
                        }))
                    }
                }
                Err(e) => Err(Error::new(ErrorDetails::Config {
                    message: format!("Failed to parse encrypted PKCS#8 from {source}: {e}"),
                })),
            }
        } else {
            // Try OpenSSL-style encrypted keys
            tracing::debug!("PEM does not contain 'ENCRYPTED PRIVATE KEY', checking for OpenSSL-style encryption");

            // Check for OpenSSL encryption headers
            if pem_content.contains("Proc-Type:") && pem_content.contains("DEK-Info:") {
                Err(Error::new(ErrorDetails::Config {
                    message: format!(
                        "RSA private key from {source} appears to be encrypted with legacy OpenSSL format. Please convert to PKCS#8 format using: openssl pkcs8 -topk8 -in old_key.pem -out new_key.pem"
                    ),
                }))
            } else {
                Err(Error::new(ErrorDetails::Config {
                    message: format!(
                        "Failed to parse RSA private key from {source}: not a valid PKCS#1, PKCS#8, or encrypted PKCS#8 format"
                    ),
                }))
            }
        }
    } else {
        let pem_header = pem_content.lines().next().unwrap_or("");
        if pem_header.contains("ENCRYPTED") {
            Err(Error::new(ErrorDetails::Config {
                message: format!(
                    "RSA private key from {source} appears to be encrypted. Please set TENSORZERO_RSA_PRIVATE_KEY_PASSWORD environment variable"
                ),
            }))
        } else {
            Err(Error::new(ErrorDetails::Config {
                message: format!(
                    "Failed to parse RSA private key from {source}: not a valid PKCS#1 or PKCS#8 format"
                ),
            }))
        }
    }
}

/// Load RSA private key from environment variable or file
pub fn load_private_key() -> Result<Option<RsaPrivateKey>, Error> {
    // Check for inline PEM content first
    if let Ok(pem_content) = env::var("TENSORZERO_RSA_PRIVATE_KEY") {
        let private_key = parse_private_key_from_pem(&pem_content, "environment variable")?;
        return Ok(Some(private_key));
    }

    // Check for file path
    if let Ok(key_path) = env::var("TENSORZERO_RSA_PRIVATE_KEY_PATH") {
        let pem_content = std::fs::read_to_string(&key_path).map_err(|e| {
            Error::new(ErrorDetails::Config {
                message: format!("Failed to read RSA private key from file '{key_path}': {e}"),
            })
        })?;

        let private_key = parse_private_key_from_pem(&pem_content, &format!("file '{key_path}'"))?;
        return Ok(Some(private_key));
    }

    // No private key configured - decryption is optional
    Ok(None)
}

/// Decrypt an RSA-encrypted string
pub fn decrypt_api_key(
    private_key: &RsaPrivateKey,
    encrypted_data: &str,
) -> Result<SecretString, Error> {
    // First, try to decode the encrypted data
    // Check if it's hex-encoded (all characters are valid hex)
    let encrypted_bytes = if encrypted_data.chars().all(|c| c.is_ascii_hexdigit()) {
        // Try hex decoding
        hex::decode(encrypted_data).map_err(|e| {
            Error::new(ErrorDetails::Config {
                message: format!("Failed to decode hex encrypted data: {e}"),
            })
        })?
    } else {
        // Try base64 decoding
        BASE64.decode(encrypted_data).map_err(|e| {
            Error::new(ErrorDetails::Config {
                message: format!("Failed to decode base64 encrypted data: {e}"),
            })
        })?
    };

    // Try OAEP first (as that's what the Python service seems to use)
    let decrypted_bytes = match private_key.decrypt(Oaep::new::<Sha256>(), &encrypted_bytes) {
        Ok(bytes) => {
            tracing::debug!("Successfully decrypted API key using OAEP padding");
            bytes
        }
        Err(oaep_err) => {
            // Fall back to PKCS#1 v1.5 if OAEP fails
            tracing::debug!("OAEP decryption failed, trying PKCS1v15: {}", oaep_err);
            private_key
                .decrypt(Pkcs1v15Encrypt, &encrypted_bytes)
                .map_err(|pkcs_err| {
                    Error::new(ErrorDetails::Config {
                        message: format!(
                            "Failed to decrypt API key with both OAEP and PKCS1v15. OAEP error: {oaep_err}, PKCS1v15 error: {pkcs_err}"
                        ),
                    })
                })?
        }
    };

    // Convert to string
    let decrypted_string = String::from_utf8(decrypted_bytes).map_err(|e| {
        Error::new(ErrorDetails::Config {
            message: format!("Decrypted data is not valid UTF-8: {e}"),
        })
    })?;

    Ok(SecretString::from(decrypted_string))
}

/// Check if RSA decryption is enabled
pub fn is_decryption_enabled() -> bool {
    env::var("TENSORZERO_RSA_PRIVATE_KEY").is_ok()
        || env::var("TENSORZERO_RSA_PRIVATE_KEY_PATH").is_ok()
}

#[cfg(test)]
mod tests {
    use super::*;
    use rsa::{pkcs1::EncodeRsaPrivateKey, pkcs1::EncodeRsaPublicKey, RsaPublicKey};
    use secrecy::ExposeSecret;

    // Generate a test RSA key pair
    fn generate_test_keypair() -> (RsaPrivateKey, RsaPublicKey) {
        use rsa::rand_core::OsRng;
        // Use a smaller key size for tests to speed them up
        let bits = 1024;
        let private_key = RsaPrivateKey::new(&mut OsRng, bits).expect("failed to generate key");
        let public_key = RsaPublicKey::from(&private_key);
        (private_key, public_key)
    }

    #[test]
    fn test_decrypt_api_key_pkcs1v15() {
        let (private_key, public_key) = generate_test_keypair();
        let test_api_key = "test-api-key-12345";

        // Encrypt the test API key with PKCS1v15
        use rsa::rand_core::OsRng;
        let encrypted = public_key
            .encrypt(&mut OsRng, Pkcs1v15Encrypt, test_api_key.as_bytes())
            .expect("encryption failed");
        let encrypted_base64 = BASE64.encode(&encrypted);

        // Decrypt and verify
        let decrypted =
            decrypt_api_key(&private_key, &encrypted_base64).expect("decryption failed");

        // Compare using expose_secret() for testing
        assert_eq!(decrypted.expose_secret(), test_api_key);
    }

    #[test]
    fn test_decrypt_api_key_oaep() {
        let (private_key, public_key) = generate_test_keypair();
        let test_api_key = "test-api-key-12345";

        // Encrypt the test API key with OAEP
        use rsa::rand_core::OsRng;
        let encrypted = public_key
            .encrypt(&mut OsRng, Oaep::new::<Sha256>(), test_api_key.as_bytes())
            .expect("encryption failed");
        let encrypted_base64 = BASE64.encode(&encrypted);

        // Decrypt and verify
        let decrypted =
            decrypt_api_key(&private_key, &encrypted_base64).expect("decryption failed");

        // Compare using expose_secret() for testing
        assert_eq!(decrypted.expose_secret(), test_api_key);
    }

    #[test]
    fn test_decrypt_api_key_hex() {
        let (private_key, public_key) = generate_test_keypair();
        let test_api_key = "test-api-key-12345";

        // Encrypt the test API key with OAEP (like the Python service)
        use rsa::rand_core::OsRng;
        let encrypted = public_key
            .encrypt(&mut OsRng, Oaep::new::<Sha256>(), test_api_key.as_bytes())
            .expect("encryption failed");
        let encrypted_hex = hex::encode(&encrypted);

        // Decrypt and verify
        let decrypted = decrypt_api_key(&private_key, &encrypted_hex).expect("decryption failed");

        // Compare using expose_secret() for testing
        assert_eq!(decrypted.expose_secret(), test_api_key);
    }

    #[test]
    fn test_decrypt_invalid_base64() {
        let (private_key, _) = generate_test_keypair();
        let result = decrypt_api_key(&private_key, "not-valid-base64!");
        assert!(result.is_err());
        assert!(result.unwrap_err().to_string().contains("base64"));
    }

    #[test]
    fn test_private_key_from_pem() {
        let (private_key, _) = generate_test_keypair();
        let pem_string = private_key
            .to_pkcs1_pem(rsa::pkcs1::LineEnding::LF)
            .expect("failed to encode PEM")
            .to_string();

        // Test parsing PEM
        let parsed_key = RsaPrivateKey::from_pkcs1_pem(&pem_string).expect("failed to parse PEM");

        // Verify the keys are equivalent by comparing their public keys
        let original_public = RsaPublicKey::from(&private_key);
        let parsed_public = RsaPublicKey::from(&parsed_key);

        assert_eq!(
            original_public
                .to_pkcs1_pem(rsa::pkcs1::LineEnding::LF)
                .unwrap(),
            parsed_public
                .to_pkcs1_pem(rsa::pkcs1::LineEnding::LF)
                .unwrap()
        );
    }

    #[test]
    fn test_parse_pkcs8_private_key() {
        use rsa::pkcs8::EncodePrivateKey;

        let (private_key, _) = generate_test_keypair();

        // Test PKCS#8 format without password
        let pkcs8_pem = private_key
            .to_pkcs8_pem(rsa::pkcs8::LineEnding::LF)
            .expect("failed to encode PKCS#8 PEM")
            .to_string();

        let parsed_key =
            parse_private_key_from_pem(&pkcs8_pem, "test").expect("failed to parse PKCS#8 PEM");

        // Verify the keys are equivalent
        let original_public = RsaPublicKey::from(&private_key);
        let parsed_public = RsaPublicKey::from(&parsed_key);

        assert_eq!(
            original_public
                .to_pkcs1_pem(rsa::pkcs1::LineEnding::LF)
                .unwrap(),
            parsed_public
                .to_pkcs1_pem(rsa::pkcs1::LineEnding::LF)
                .unwrap()
        );
    }

    #[test]
    fn test_parse_mixed_format_keys() {
        let (private_key, _) = generate_test_keypair();

        // Test that parse_private_key_from_pem can handle both formats
        let pkcs1_pem = private_key
            .to_pkcs1_pem(rsa::pkcs1::LineEnding::LF)
            .expect("failed to encode PKCS#1 PEM")
            .to_string();

        let parsed_pkcs1 =
            parse_private_key_from_pem(&pkcs1_pem, "test PKCS#1").expect("failed to parse PKCS#1");

        use rsa::pkcs8::EncodePrivateKey;
        let pkcs8_pem = private_key
            .to_pkcs8_pem(rsa::pkcs8::LineEnding::LF)
            .expect("failed to encode PKCS#8 PEM")
            .to_string();

        let parsed_pkcs8 =
            parse_private_key_from_pem(&pkcs8_pem, "test PKCS#8").expect("failed to parse PKCS#8");

        // Verify both parsed keys are equivalent to the original
        let original_public = RsaPublicKey::from(&private_key);
        let parsed_pkcs1_public = RsaPublicKey::from(&parsed_pkcs1);
        let parsed_pkcs8_public = RsaPublicKey::from(&parsed_pkcs8);

        let original_pem = original_public
            .to_pkcs1_pem(rsa::pkcs1::LineEnding::LF)
            .unwrap();
        assert_eq!(
            original_pem,
            parsed_pkcs1_public
                .to_pkcs1_pem(rsa::pkcs1::LineEnding::LF)
                .unwrap()
        );
        assert_eq!(
            original_pem,
            parsed_pkcs8_public
                .to_pkcs1_pem(rsa::pkcs1::LineEnding::LF)
                .unwrap()
        );
    }

    #[test]
    fn test_real_encrypted_key() {
        use rsa::traits::PublicKeyParts;

        // Test with the actual encrypted key file if it exists
        let key_path = "/datadisk/ditto/bud-serve-app/private_key.pem";
        if std::path::Path::new(key_path).exists() {
            // Set the password environment variable
            std::env::set_var("TENSORZERO_RSA_PRIVATE_KEY_PASSWORD", "qwerty12345");

            let pem_content = std::fs::read_to_string(key_path).expect("Failed to read key file");

            // This should succeed with the correct password
            let result = parse_private_key_from_pem(&pem_content, "real key file");
            assert!(
                result.is_ok(),
                "Failed to parse real encrypted key: {:?}",
                result.err()
            );

            let key = result.unwrap();
            // Verify it's a 2048-bit key
            assert_eq!(key.size() * 8, 2048);

            tracing::info!("Successfully loaded and decrypted the real private key!");
        } else {
            tracing::info!("Skipping real key test - file not found");
        }
    }
}
