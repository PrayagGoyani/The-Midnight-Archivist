import { apiPost } from './apiClient';
import type { SearchRequest, SearchResponse } from '../types/search';

export async function performSearch(
  req: SearchRequest,
  signal?: AbortSignal
): Promise<SearchResponse> {
  return apiPost<SearchResponse>('/search', req, signal);
}
