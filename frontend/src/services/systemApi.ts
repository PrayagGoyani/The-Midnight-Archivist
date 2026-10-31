import { apiGet } from './apiClient';
import type { SystemOllamaStatus, SystemStatusResponse } from '../types/system';

export async function getSystemStatus(signal?: AbortSignal): Promise<SystemStatusResponse> {
  return apiGet<SystemStatusResponse>('/system/status', signal);
}

export async function getOllamaStatus(signal?: AbortSignal): Promise<SystemOllamaStatus> {
  return apiGet<SystemOllamaStatus>('/ollama/status', signal);
}
