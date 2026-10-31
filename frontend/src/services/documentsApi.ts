import { apiDelete, apiGet, apiPost, apiUpload } from './apiClient';
import type {
  ChunkListResponse,
  DocumentListResponse,
  DocumentOut,
  ProcessingResponse,
} from '../types/document';

export async function listDocuments(signal?: AbortSignal): Promise<DocumentListResponse> {
  return apiGet<DocumentListResponse>('/documents', signal);
}

export async function getDocument(id: string, signal?: AbortSignal): Promise<DocumentOut> {
  return apiGet<DocumentOut>(`/documents/${id}`, signal);
}

export async function uploadDocument(file: File, signal?: AbortSignal): Promise<DocumentOut> {
  const formData = new FormData();
  formData.append('file', file);
  return apiUpload<DocumentOut>('/documents', formData, signal);
}

export async function deleteDocument(id: string, signal?: AbortSignal): Promise<void> {
  return apiDelete(`/documents/${id}`, signal);
}

export async function processDocument(id: string, signal?: AbortSignal): Promise<ProcessingResponse> {
  return apiPost<ProcessingResponse>(`/documents/${id}/process`, undefined, signal);
}

export async function getDocumentChunks(id: string, signal?: AbortSignal): Promise<ChunkListResponse> {
  return apiGet<ChunkListResponse>(`/documents/${id}/chunks`, signal);
}
