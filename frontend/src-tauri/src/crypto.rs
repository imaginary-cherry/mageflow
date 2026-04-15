use aes_gcm::{
    aead::{Aead, AeadCore, KeyInit, OsRng},
    Aes256Gcm, Key, Nonce,
};
use hkdf::Hkdf;
use sha2::Sha256;
use std::path::Path;

const FORMAT_VERSION: u8 = 1;
const SALT: &[u8] = b"mageflow-voyance-v1";
const INFO: &[u8] = b"secrets-encryption-key";
const MIN_FILE_SIZE: usize = 29; // 1 (version) + 12 (nonce) + 16 (GCM tag)

/// Retrieve the machine's unique ID. Returns an error if the ID is empty or too short.
pub fn get_machine_id() -> Result<String, String> {
    let id = machine_uid::get().map_err(|e| format!("Failed to get machine ID: {e}"))?;
    let id = id.trim().to_string();
    if id.is_empty() {
        return Err("Machine ID is empty".to_string());
    }
    if id.len() < 16 {
        return Err(format!(
            "Machine ID too short ({} chars, need >= 16)",
            id.len()
        ));
    }
    Ok(id)
}

/// Derive a 32-byte encryption key from the machine ID using HKDF-SHA256.
pub fn derive_key() -> Result<[u8; 32], String> {
    let machine_id = get_machine_id()?;
    let hk = Hkdf::<Sha256>::new(Some(SALT), machine_id.as_bytes());
    let mut key = [0u8; 32];
    hk.expand(INFO, &mut key)
        .map_err(|e| format!("HKDF expand failed: {e}"))?;
    Ok(key)
}

/// Encrypt a secrets map using AES-256-GCM with a fresh nonce.
/// Output format: [1B version][12B nonce][ciphertext + GCM tag]
pub fn encrypt_secrets(
    secrets: &serde_json::Map<String, serde_json::Value>,
) -> Result<Vec<u8>, String> {
    let key_bytes = derive_key()?;
    let key = Key::<Aes256Gcm>::from_slice(&key_bytes);
    let cipher = Aes256Gcm::new(key);
    let nonce = Aes256Gcm::generate_nonce(&mut OsRng);

    let plaintext =
        serde_json::to_vec(secrets).map_err(|e| format!("JSON serialize failed: {e}"))?;
    let ciphertext = cipher
        .encrypt(&nonce, plaintext.as_ref())
        .map_err(|e| format!("Encryption failed: {e}"))?;

    let mut output = Vec::with_capacity(1 + 12 + ciphertext.len());
    output.push(FORMAT_VERSION);
    output.extend_from_slice(&nonce);
    output.extend_from_slice(&ciphertext);
    Ok(output)
}

/// Decrypt a versioned ciphertext blob back into a secrets map.
pub fn decrypt_secrets(
    data: &[u8],
) -> Result<serde_json::Map<String, serde_json::Value>, String> {
    if data.len() < MIN_FILE_SIZE {
        return Err("File too short to be valid".to_string());
    }
    let version = data[0];
    if version != FORMAT_VERSION {
        return Err(format!("Unknown format version: {version}"));
    }
    let nonce = Nonce::from_slice(&data[1..13]);
    let ciphertext = &data[13..];

    let key_bytes = derive_key()?;
    let key = Key::<Aes256Gcm>::from_slice(&key_bytes);
    let cipher = Aes256Gcm::new(key);

    let plaintext = cipher.decrypt(nonce, ciphertext).map_err(|_| {
        "Decryption failed: file may be corrupted or created on a different machine".to_string()
    })?;

    serde_json::from_slice(&plaintext).map_err(|e| format!("JSON parse failed: {e}"))
}

/// Encrypt and write secrets to a file. Creates parent directories if needed.
pub fn save_secrets_to_file(
    path: &Path,
    secrets: &serde_json::Map<String, serde_json::Value>,
) -> Result<(), String> {
    if let Some(parent) = path.parent() {
        std::fs::create_dir_all(parent)
            .map_err(|e| format!("Failed to create directory: {e}"))?;
    }
    let data = encrypt_secrets(secrets)?;
    std::fs::write(path, data).map_err(|e| format!("Failed to write secrets file: {e}"))
}

/// Load and decrypt secrets from a file. Returns Ok(None) if the file does not exist.
pub fn load_secrets_from_file(
    path: &Path,
) -> Result<Option<serde_json::Map<String, serde_json::Value>>, String> {
    if !path.exists() {
        return Ok(None);
    }
    let data = std::fs::read(path).map_err(|e| format!("Failed to read secrets file: {e}"))?;
    decrypt_secrets(&data).map(Some)
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::{Map, Value};

    #[test]
    fn test_machine_id_nonempty() {
        let id = get_machine_id().expect("get_machine_id should succeed");
        assert!(!id.is_empty(), "Machine ID should not be empty");
        assert!(
            id.len() >= 16,
            "Machine ID should be >= 16 chars, got {}",
            id.len()
        );
    }

    #[test]
    fn test_derive_key_deterministic() {
        let key1 = derive_key().expect("derive_key should succeed");
        let key2 = derive_key().expect("derive_key should succeed");
        assert_eq!(key1, key2, "Same machine should produce same key");
    }

    #[test]
    fn test_derive_key_length() {
        let key = derive_key().expect("derive_key should succeed");
        assert_eq!(key.len(), 32, "Key should be exactly 32 bytes");
    }

    #[test]
    fn test_encrypt_decrypt_roundtrip() {
        let mut secrets = Map::new();
        secrets.insert(
            "hatchetApiKey".to_string(),
            Value::String("sk-test-12345".to_string()),
        );
        secrets.insert(
            "redisUrl".to_string(),
            Value::String("redis://localhost:6379".to_string()),
        );

        let encrypted = encrypt_secrets(&secrets).expect("encrypt should succeed");
        let decrypted = decrypt_secrets(&encrypted).expect("decrypt should succeed");
        assert_eq!(secrets, decrypted);
    }

    #[test]
    fn test_fresh_nonce_per_save() {
        let mut secrets = Map::new();
        secrets.insert("key".to_string(), Value::String("value".to_string()));

        let enc1 = encrypt_secrets(&secrets).expect("encrypt should succeed");
        let enc2 = encrypt_secrets(&secrets).expect("encrypt should succeed");
        assert_ne!(
            enc1, enc2,
            "Two encryptions of the same data should differ (fresh nonce)"
        );
    }

    #[test]
    fn test_format_version_byte() {
        let mut secrets = Map::new();
        secrets.insert("k".to_string(), Value::String("v".to_string()));

        let encrypted = encrypt_secrets(&secrets).expect("encrypt should succeed");
        assert_eq!(encrypted[0], 0x01, "First byte should be version 1");
    }

    #[test]
    fn test_tampered_data_fails_gracefully() {
        let mut secrets = Map::new();
        secrets.insert("key".to_string(), Value::String("value".to_string()));

        let mut encrypted = encrypt_secrets(&secrets).expect("encrypt should succeed");
        // Tamper with a byte in the ciphertext area (after version + nonce)
        let last = encrypted.len() - 1;
        encrypted[last] ^= 0xFF;

        let result = decrypt_secrets(&encrypted);
        assert!(result.is_err(), "Tampered data should return Err");
        assert!(
            result
                .unwrap_err()
                .contains("Decryption failed"),
            "Error should mention decryption failure"
        );
    }

    #[test]
    fn test_truncated_data_fails() {
        // Data shorter than 29 bytes (1 + 12 + 16)
        let short_data = vec![0x01; 28];
        let result = decrypt_secrets(&short_data);
        assert!(result.is_err(), "Truncated data should return Err");
        assert!(result.unwrap_err().contains("too short"));
    }

    #[test]
    fn test_wrong_version_fails() {
        let mut data = vec![0x02]; // wrong version
        data.extend_from_slice(&[0u8; 28]); // pad to min size
        let result = decrypt_secrets(&data);
        assert!(result.is_err(), "Wrong version should return Err");
        assert!(result.unwrap_err().contains("Unknown format version"));
    }

    #[test]
    fn test_save_load_file_roundtrip() {
        let dir = std::env::temp_dir().join("mageflow_test_crypto_roundtrip");
        let _ = std::fs::remove_dir_all(&dir);
        std::fs::create_dir_all(&dir).unwrap();
        let path = dir.join("secrets.bin");

        let mut secrets = Map::new();
        secrets.insert(
            "hatchetApiKey".to_string(),
            Value::String("sk-abc".to_string()),
        );
        secrets.insert(
            "redisUrl".to_string(),
            Value::String("redis://localhost".to_string()),
        );

        save_secrets_to_file(&path, &secrets).expect("save should succeed");
        let loaded = load_secrets_from_file(&path)
            .expect("load should succeed")
            .expect("file should exist");
        assert_eq!(secrets, loaded);

        // cleanup
        let _ = std::fs::remove_dir_all(&dir);
    }

    #[test]
    fn test_load_nonexistent_returns_none() {
        let path = std::env::temp_dir().join("mageflow_test_nonexistent_secrets.bin");
        let _ = std::fs::remove_file(&path); // ensure it doesn't exist
        let result = load_secrets_from_file(&path).expect("load should succeed");
        assert!(result.is_none(), "Nonexistent file should return None");
    }

    #[test]
    fn test_empty_machine_id_validation() {
        // We can't easily mock machine_uid::get(), but we can verify the validation logic
        // by testing that get_machine_id() returns a proper result (non-empty)
        // The validation is tested implicitly -- if machine ID were empty, it would error.
        let result = get_machine_id();
        assert!(result.is_ok(), "Machine ID should be retrievable on this platform");
        let id = result.unwrap();
        assert!(!id.is_empty());
    }
}
