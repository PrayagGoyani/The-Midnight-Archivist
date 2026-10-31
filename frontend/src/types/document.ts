export type DocumentStatus = 'uploaded' | 'processing' | 'ready' | 'failed';

export interface DocumentOut {
  id: string;
  title: string;
  original_filename: string;
  file_extension: string;
  content_type: string;
  file_size: number;
  status: DocumentStatus;
  error_message?: string | null;
  page_count?: number | null;
  indexed_at?: string | null;
  embedding_model_used?: string | null;
  chunk_count?: number | null;
  reindex_error?: string | null;
  created_at: string;
  updated_at: string;
}

export interface DocumentListResponse {
  documents: DocumentOut[];
  total: number;
}

export interface ProcessingResponse {
  document_id: string;
  title: string;
  status: DocumentStatus;
  chunk_count: number;
  embedding_model: string;
  dimensions: number;
  indexed_at: string;
}

export interface ChunkOut {
  id: string;
  document_id: string;
  chunk_index: number;
  text: string;
  page_number?: number | null;
  section?: string | null;
  embedding_model?: string | null;
  created_at: string;
}

export interface ChunkListResponse {
  chunks: ChunkOut[];
  total: number;
  document_id: string;
}
