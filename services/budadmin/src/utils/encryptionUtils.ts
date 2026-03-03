import ByteBuffer from "bytebuffer";
import { Console } from "console";
import forge from "node-forge";

const password = process.env.NEXT_PUBLIC_PASSWORD;
const privateKeyString = process.env.NEXT_PUBLIC_PRIVATE_KEY;

const base64Decode = (base64: string | undefined) => {
  if (!base64) {
    throw new Error("base64Decode: Input is undefined or empty");
  }
  if (typeof window !== "undefined") {
    // Client-side (browser)
    return atob(base64);
  } else {
    // Server-side (Node.js)
    return Buffer.from(base64, "base64").toString("utf-8");
  }
};

// Decode private key if available
let decodedString: string | null = null;
try {
  if (privateKeyString) {
    decodedString = base64Decode(privateKeyString);
  }
} catch (error) {
  console.error("Failed to decode private key:", error);
}

export async function decryptString(
  encrypedKey: string,
): Promise<string | null> {
  try {
    if (!encrypedKey || typeof encrypedKey !== "string") {
      return null;
    }

    // Check if private key is available
    if (!decodedString) {
      throw new Error(
        "Private key not available - check NEXT_PUBLIC_PRIVATE_KEY environment variable",
      );
    }

    // Convert to base64 string
    const byteBuffer = ByteBuffer.fromHex(encrypedKey);
    const base64String = byteBuffer.toBase64().toString();

    // Load private key with password
    const privateKey = forge.pki.decryptRsaPrivateKey(decodedString, password);
    if (!privateKey) {
      throw new Error("Failed to decrypt private key");
    }

    // Decode base64 string
    const messageEncryptedBytes = forge.util.decode64(base64String);

    // Decrypt the encrypted message using the private key
    const messageDecrypted = privateKey.decrypt(
      messageEncryptedBytes,
      "RSA-OAEP",
      {
        md: forge.md.sha256.create(),
        mgf1: {
          md: forge.md.sha256.create(),
        },
      },
    );
    // Convert the decrypted message to a string
    return messageDecrypted;
  } catch (error) {
    console.error("Decryption error:", error);
    return null; // or handle the error in some other way
  }
}
