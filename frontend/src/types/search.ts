export interface SearchRequest {
  query: string;
  document_ids?: string[];
  top_k?: number;
}

export interface SearchResultItem {
  chunk_id: string;
  document_id: string;
  document_title: string;
  text: string;
  page_number?: number | null;
  section?: string | null;
  similarity_score: number;
}

export interface SearchResponse {
  query: string;
  total: number;
  embedding_model: string;
  results: SearchResultItem[];
}
