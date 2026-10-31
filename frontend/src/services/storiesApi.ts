import { apiDelete, apiGet, apiPost } from './apiClient';
import type {
  FullStoryNarrativeResponse,
  StoryBranchesResponse,
  StoryContinueRequest,
  StoryGenerateRequest,
  StoryGenerationResponse,
  StoryListResponse,
  StoryOut,
} from '../types/story';

export async function generateStory(
  req: StoryGenerateRequest,
  signal?: AbortSignal
): Promise<StoryGenerationResponse> {
  return apiPost<StoryGenerationResponse>('/stories/generate', req, signal);
}

export async function continueStory(
  storyId: string,
  req: StoryContinueRequest,
  signal?: AbortSignal
): Promise<StoryGenerationResponse> {
  return apiPost<StoryGenerationResponse>(`/stories/${storyId}/continue`, req, signal);
}

export async function getFullNarrative(
  storyId: string,
  signal?: AbortSignal
): Promise<FullStoryNarrativeResponse> {
  return apiGet<FullStoryNarrativeResponse>(`/stories/${storyId}/full`, signal);
}

export async function getStoryBranches(
  storyId: string,
  signal?: AbortSignal
): Promise<StoryBranchesResponse> {
  return apiGet<StoryBranchesResponse>(`/stories/${storyId}/branches`, signal);
}

export async function listStories(signal?: AbortSignal): Promise<StoryListResponse> {
  return apiGet<StoryListResponse>('/stories', signal);
}

export async function getStory(storyId: string, signal?: AbortSignal): Promise<StoryOut> {
  return apiGet<StoryOut>(`/stories/${storyId}`, signal);
}

export async function deleteStory(storyId: string, signal?: AbortSignal): Promise<void> {
  return apiDelete(`/stories/${storyId}`, signal);
}
