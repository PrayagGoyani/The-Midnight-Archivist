export interface SystemDatabaseStatus {
  status: string;
  engine: string;
  path: string;
}

export interface SystemOllamaStatus {
  status: string;
  base_url: string;
  generation_model: string;
  generation_model_available: boolean;
  embedding_model: string;
  embedding_model_available: boolean;
  available_models: string[];
}

export interface SystemStorageStatus {
  data_dir: string;
  upload_dir: string;
  max_upload_size_mb: number;
  document_count: number;
  chunk_count: number;
  story_count: number;
}

export interface SystemStatusResponse {
  status: string;
  version: string;
  database: SystemDatabaseStatus;
  ollama: SystemOllamaStatus;
  storage: SystemStorageStatus;
}
