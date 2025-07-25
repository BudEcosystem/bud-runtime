use crate::error::{Error, ErrorDetails};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::path::PathBuf;
use tokio::fs;
use uuid::Uuid;

/// Configuration for file storage
#[derive(Debug, Clone, Deserialize, Serialize)]
#[serde(tag = "type", rename_all = "snake_case")]
pub enum FileStorageConfig {
    Local {
        path: PathBuf,
    },
    S3 {
        bucket: String,
        region: String,
        access_key: Option<String>,
        secret_key: Option<String>,
    },
}

impl Default for FileStorageConfig {
    fn default() -> Self {
        Self::Local {
            path: PathBuf::from("/tmp/tensorzero/files"),
        }
    }
}

/// File metadata for tracking uploaded files
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FileMetadata {
    pub id: String,
    pub filename: String,
    pub size: u64,
    pub content_type: String,
    pub created_at: i64,
    pub purpose: String, // e.g., "batch"
}

/// File storage interface
#[async_trait::async_trait]
pub trait FileStorage: Send + Sync {
    /// Store a file and return its ID
    async fn store_file(
        &self,
        content: Vec<u8>,
        filename: String,
        content_type: String,
        purpose: String,
    ) -> Result<FileMetadata, Error>;

    /// Retrieve file content by ID
    async fn get_file_content(&self, file_id: &str) -> Result<Vec<u8>, Error>;

    /// Get file metadata by ID
    async fn get_file_metadata(&self, file_id: &str) -> Result<FileMetadata, Error>;

    /// Delete a file by ID
    async fn delete_file(&self, file_id: &str) -> Result<(), Error>;

    /// List files (for cleanup/management)
    async fn list_files(&self) -> Result<Vec<FileMetadata>, Error>;
}

/// Local filesystem storage implementation
pub struct LocalFileStorage {
    base_path: PathBuf,
    metadata_store: tokio::sync::RwLock<HashMap<String, FileMetadata>>,
}

impl LocalFileStorage {
    pub async fn new(base_path: PathBuf) -> Result<Self, Error> {
        // Create directory if it doesn't exist
        fs::create_dir_all(&base_path).await.map_err(|e| {
            Error::new(ErrorDetails::InvalidRequest {
                message: format!("Failed to create file storage directory: {e}"),
            })
        })?;

        let metadata_store = tokio::sync::RwLock::new(HashMap::new());

        // TODO: Load existing metadata from disk if needed

        Ok(Self {
            base_path,
            metadata_store,
        })
    }

    fn get_file_path(&self, file_id: &str) -> PathBuf {
        self.base_path.join(format!("{file_id}.data"))
    }

    fn get_metadata_path(&self, file_id: &str) -> PathBuf {
        self.base_path.join(format!("{file_id}.meta"))
    }

    async fn save_metadata(&self, metadata: &FileMetadata) -> Result<(), Error> {
        let metadata_path = self.get_metadata_path(&metadata.id);
        let metadata_json = serde_json::to_string_pretty(metadata).map_err(|e| {
            Error::new(ErrorDetails::Serialization {
                message: format!("Failed to serialize file metadata: {e}"),
            })
        })?;

        fs::write(metadata_path, metadata_json).await.map_err(|e| {
            Error::new(ErrorDetails::InvalidRequest {
                message: format!("Failed to save file metadata: {e}"),
            })
        })?;

        // Also store in memory for fast access
        let mut store = self.metadata_store.write().await;
        store.insert(metadata.id.clone(), metadata.clone());

        Ok(())
    }

    async fn load_metadata(&self, file_id: &str) -> Result<FileMetadata, Error> {
        // Try memory cache first
        {
            let store = self.metadata_store.read().await;
            if let Some(metadata) = store.get(file_id) {
                return Ok(metadata.clone());
            }
        }

        // Load from disk
        let metadata_path = self.get_metadata_path(file_id);
        let metadata_json = fs::read_to_string(metadata_path).await.map_err(|e| {
            if e.kind() == std::io::ErrorKind::NotFound {
                Error::new(ErrorDetails::InvalidRequest {
                    message: format!("File not found: {file_id}"),
                })
            } else {
                Error::new(ErrorDetails::InvalidRequest {
                    message: format!("Failed to read file metadata: {e}"),
                })
            }
        })?;

        let metadata: FileMetadata = serde_json::from_str(&metadata_json).map_err(|e| {
            Error::new(ErrorDetails::Serialization {
                message: format!("Failed to parse file metadata: {e}"),
            })
        })?;

        // Cache in memory
        {
            let mut store = self.metadata_store.write().await;
            store.insert(file_id.to_string(), metadata.clone());
        }

        Ok(metadata)
    }
}

#[async_trait::async_trait]
impl FileStorage for LocalFileStorage {
    async fn store_file(
        &self,
        content: Vec<u8>,
        filename: String,
        content_type: String,
        purpose: String,
    ) -> Result<FileMetadata, Error> {
        let file_id = format!("file-{}", Uuid::now_v7());
        let file_path = self.get_file_path(&file_id);

        // Write file content
        fs::write(&file_path, &content).await.map_err(|e| {
            Error::new(ErrorDetails::InvalidRequest {
                message: format!("Failed to write file: {e}"),
            })
        })?;

        // Create metadata
        let metadata = FileMetadata {
            id: file_id,
            filename,
            size: content.len() as u64,
            content_type,
            created_at: chrono::Utc::now().timestamp(),
            purpose,
        };

        // Save metadata
        self.save_metadata(&metadata).await?;

        Ok(metadata)
    }

    async fn get_file_content(&self, file_id: &str) -> Result<Vec<u8>, Error> {
        // Verify file exists by checking metadata
        self.load_metadata(file_id).await?;

        let file_path = self.get_file_path(file_id);
        fs::read(&file_path).await.map_err(|e| {
            Error::new(ErrorDetails::InvalidRequest {
                message: format!("Failed to read file: {e}"),
            })
        })
    }

    async fn get_file_metadata(&self, file_id: &str) -> Result<FileMetadata, Error> {
        self.load_metadata(file_id).await
    }

    async fn delete_file(&self, file_id: &str) -> Result<(), Error> {
        // Remove from memory cache
        {
            let mut store = self.metadata_store.write().await;
            store.remove(file_id);
        }

        // Delete files from disk
        let file_path = self.get_file_path(file_id);
        let metadata_path = self.get_metadata_path(file_id);

        // Ignore errors if files don't exist
        let _ = fs::remove_file(file_path).await;
        let _ = fs::remove_file(metadata_path).await;

        Ok(())
    }

    async fn list_files(&self) -> Result<Vec<FileMetadata>, Error> {
        let store = self.metadata_store.read().await;
        Ok(store.values().cloned().collect())
    }
}

/// Create a file storage instance based on configuration
pub async fn create_file_storage(
    config: &FileStorageConfig,
) -> Result<Box<dyn FileStorage>, Error> {
    match config {
        FileStorageConfig::Local { path } => {
            let storage = LocalFileStorage::new(path.clone()).await?;
            Ok(Box::new(storage))
        }
        FileStorageConfig::S3 { .. } => {
            // TODO: Implement S3 storage
            Err(Error::new(ErrorDetails::InvalidRequest {
                message: "S3 storage not yet implemented".to_string(),
            }))
        }
    }
}

/// Validate uploaded file for batch processing
pub fn validate_batch_file(
    content: &[u8],
    filename: &str,
    content_type: &str,
) -> Result<(), Error> {
    // Check file size (max 100MB)
    const MAX_FILE_SIZE: usize = 100 * 1024 * 1024;
    if content.len() > MAX_FILE_SIZE {
        return Err(Error::new(ErrorDetails::InvalidRequest {
            message: format!(
                "File too large: {} bytes (max {} bytes)",
                content.len(),
                MAX_FILE_SIZE
            ),
        }));
    }

    // Check file extension
    if !filename.ends_with(".jsonl") {
        return Err(Error::new(ErrorDetails::InvalidRequest {
            message: "File must have .jsonl extension".to_string(),
        }));
    }

    // Check content type
    if content_type != "application/jsonl"
        && content_type != "text/plain"
        && content_type != "application/octet-stream"
    {
        return Err(Error::new(ErrorDetails::InvalidRequest {
            message: format!(
                "Invalid content type: {content_type}, expected application/jsonl or text/plain"
            ),
        }));
    }

    // Basic UTF-8 validation
    let content_str = std::str::from_utf8(content).map_err(|_| {
        Error::new(ErrorDetails::InvalidRequest {
            message: "File must be valid UTF-8".to_string(),
        })
    })?;

    // Validate JSONL format
    for (line_num, line) in content_str.lines().enumerate() {
        if line.trim().is_empty() {
            continue; // Skip empty lines
        }

        // Try to parse as JSON
        if let Err(e) = serde_json::from_str::<serde_json::Value>(line) {
            return Err(Error::new(ErrorDetails::InvalidRequest {
                message: format!("Invalid JSONL at line {}: {}", line_num + 1, e),
            }));
        }
    }

    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use tempfile::TempDir;

    #[tokio::test]
    async fn test_local_file_storage() {
        let temp_dir = TempDir::new().unwrap();
        let storage = LocalFileStorage::new(temp_dir.path().to_path_buf())
            .await
            .unwrap();

        let content = b"test content".to_vec();
        let metadata = storage
            .store_file(
                content.clone(),
                "test.txt".to_string(),
                "text/plain".to_string(),
                "test".to_string(),
            )
            .await
            .unwrap();

        assert_eq!(metadata.filename, "test.txt");
        assert_eq!(metadata.size, content.len() as u64);

        let retrieved_content = storage.get_file_content(&metadata.id).await.unwrap();
        assert_eq!(retrieved_content, content);

        let retrieved_metadata = storage.get_file_metadata(&metadata.id).await.unwrap();
        assert_eq!(retrieved_metadata.id, metadata.id);

        storage.delete_file(&metadata.id).await.unwrap();

        let result = storage.get_file_content(&metadata.id).await;
        assert!(result.is_err());
    }

    #[test]
    fn test_validate_batch_file() {
        let valid_content = b"{}";
        assert!(validate_batch_file(valid_content, "test.jsonl", "application/jsonl").is_ok());

        // Test file size limit
        let large_content = vec![0u8; 300 * 1024 * 1024]; // 300MB
        assert!(validate_batch_file(&large_content, "test.jsonl", "application/jsonl").is_err());

        // Test file extension
        assert!(validate_batch_file(valid_content, "test.txt", "application/jsonl").is_err());

        // Test invalid UTF-8
        let invalid_utf8 = vec![0xFF, 0xFE];
        assert!(validate_batch_file(&invalid_utf8, "test.jsonl", "application/jsonl").is_err());
    }
}
