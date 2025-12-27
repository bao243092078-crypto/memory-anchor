import type { Memory, SearchRequest, MemoryLayer, NoteCategory } from '../types';

const API_BASE = '/api/v1';

/**
 * Search memories with semantic search
 */
export async function searchMemories(request: SearchRequest): Promise<Memory[]> {
  const response = await fetch(`${API_BASE}/search`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      query: request.query,
      layer: request.layer,
      category: request.category,
      limit: request.limit || 20,
    }),
  });

  if (!response.ok) {
    throw new Error(`Search failed: ${response.statusText}`);
  }

  const data = await response.json();
  return data.results || data.memories || [];
}

/**
 * List all memories with optional filters
 */
export async function listMemories(params?: {
  layer?: MemoryLayer;
  category?: NoteCategory;
  limit?: number;
  offset?: number;
}): Promise<Memory[]> {
  const searchParams = new URLSearchParams();
  if (params?.layer) searchParams.set('layer', params.layer);
  if (params?.category) searchParams.set('category', params.category);
  if (params?.limit) searchParams.set('limit', params.limit.toString());
  if (params?.offset) searchParams.set('offset', params.offset.toString());

  const url = `${API_BASE}/notes${searchParams.toString() ? '?' + searchParams.toString() : ''}`;
  const response = await fetch(url);

  if (!response.ok) {
    throw new Error(`List failed: ${response.statusText}`);
  }

  const data = await response.json();
  return data.notes || data || [];
}

/**
 * Get constitution (L0 identity schema)
 */
export async function getConstitution(): Promise<Memory[]> {
  const response = await fetch(`${API_BASE}/constitution`);

  if (!response.ok) {
    throw new Error(`Get constitution failed: ${response.statusText}`);
  }

  const data = await response.json();
  // Constitution returns entries, map them to Memory format
  const entries = data.entries || data || [];
  return entries.map((entry: { id: string; content: string; category?: NoteCategory; created_at?: string }) => ({
    id: entry.id,
    content: entry.content,
    layer: 'identity_schema' as MemoryLayer,
    category: entry.category,
    confidence: 1.0,
    created_at: entry.created_at || new Date().toISOString(),
  }));
}

/**
 * Get a single memory by ID
 */
export async function getMemory(id: string): Promise<Memory | null> {
  const response = await fetch(`${API_BASE}/notes/${id}`);

  if (response.status === 404) {
    return null;
  }

  if (!response.ok) {
    throw new Error(`Get memory failed: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Verify a memory (set confidence to 1.0)
 */
export async function verifyMemory(id: string): Promise<Memory> {
  const response = await fetch(`${API_BASE}/notes/${id}/verify`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ verified_by: 'human' }),
  });

  if (!response.ok) {
    throw new Error(`Verify failed: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Delete a memory (soft delete)
 */
export async function deleteMemory(id: string): Promise<void> {
  const response = await fetch(`${API_BASE}/notes/${id}`, {
    method: 'DELETE',
  });

  if (!response.ok) {
    throw new Error(`Delete failed: ${response.statusText}`);
  }
}

/**
 * Update a memory
 */
export async function updateMemory(
  id: string,
  data: {
    content?: string;
    session_id?: string;
    related_files?: string[];
  }
): Promise<Memory> {
  const response = await fetch(`${API_BASE}/notes/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });

  if (!response.ok) {
    throw new Error(`Update failed: ${response.statusText}`);
  }

  return response.json();
}
