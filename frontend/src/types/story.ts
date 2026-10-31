export interface BranchChoice {
  id: string;
  label: string;
  description: string;
}

export type NarrativeLength = 'short' | 'medium' | 'long';
export type GroundingMode = 'archive' | 'freeform';

export interface SourceReference {
  document_id?: string;
  document_title?: string;
  page_number?: number | null;
  section?: string | null;
  text?: string;
  similarity_score?: number;
  [key: string]: any;
}

export interface StoryGenerateRequest {
  premise: string;
  atmosphere: string;
  length: NarrativeLength;
  grounding_mode: GroundingMode;
  document_ids?: string[];
  top_k?: number;
}

export interface StoryContinueRequest {
  choice_id: string;
}

export interface StoryOut {
  id: string;
  title: string;
  premise: string;
  atmosphere: string;
  requested_length: string;
  grounding_mode: string;
  body: string;
  source_references?: string | null;
  parent_story_id?: string | null;
  branch_choice?: string | null;
  branch_choices?: string | null;
  word_count?: number | null;
  generation_model?: string | null;
  status?: string | null;
  created_at: string;
  updated_at: string;
}

export interface StoryGenerationResponse {
  id: string;
  title: string;
  content: string;
  body: string;
  premise: string;
  atmosphere: string;
  requested_length: string;
  grounding_mode: string;
  branch_choices: BranchChoice[];
  source_references: SourceReference[];
  parent_story_id?: string | null;
  branch_choice?: string | null;
  word_count: number;
  generation_model: string;
  status: string;
  created_at: string;
}

export interface NarrativeSegment {
  story_id: string;
  title: string;
  branch_label?: string | null;
  content: string;
  word_count?: number | null;
  created_at: string;
}

export interface FullStoryNarrativeResponse {
  story_id: string;
  title: string;
  premise: string;
  atmosphere: string;
  grounding_mode: string;
  full_content: string;
  total_word_count: number;
  segments: NarrativeSegment[];
  available_choices: BranchChoice[];
  source_references: SourceReference[];
}

export interface ChildBranchNode {
  story_id: string;
  branch_label?: string | null;
  title: string;
  preview: string;
  created_at: string;
}

export interface StoryBranchesResponse {
  story_id: string;
  title: string;
  available_choices: BranchChoice[];
  child_branches: ChildBranchNode[];
}

export interface StoryListResponse {
  stories: StoryOut[];
  total: number;
}
