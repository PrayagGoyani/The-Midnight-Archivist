export class ApiError extends Error {
  status: number;
  detail: any;

  constructor(status: number, message: string, detail?: any) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.detail = detail;
  }
}

const API_BASE = (import.meta.env.VITE_API_URL || '/api').replace(/\/$/, '');

async function parseErrorResponse(res: Response): Promise<ApiError> {
  const status = res.status;
  let message = `Request failed with status ${status}`;
  let detail: any = null;

  try {
    const contentType = res.headers.get('content-type') || '';
    if (contentType.includes('application/json')) {
      const data = await res.json();
      detail = data;
      if (typeof data.detail === 'string') {
        message = data.detail;
      } else if (Array.isArray(data.detail)) {
        // FastAPI validation errors
        message = data.detail.map((err: any) => err.msg || JSON.stringify(err)).join('; ');
      } else if (data.message) {
        message = data.message;
      }
    } else {
      const text = await res.text();
      if (text) {
        message = text.length > 200 ? text.slice(0, 200) + '...' : text;
      }
    }
  } catch {
    // Keep fallback message
  }

  return new ApiError(status, message, detail);
}

export async function apiGet<T>(path: string, signal?: AbortSignal): Promise<T> {
  const url = `${API_BASE}${path.startsWith('/') ? path : `/${path}`}`;
  const res = await fetch(url, {
    method: 'GET',
    headers: {
      'Accept': 'application/json',
    },
    signal,
  });

  if (!res.ok) {
    throw await parseErrorResponse(res);
  }

  return (await res.json()) as T;
}

export async function apiPost<T>(path: string, body?: any, signal?: AbortSignal): Promise<T> {
  const url = `${API_BASE}${path.startsWith('/') ? path : `/${path}`}`;
  const res = await fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Accept': 'application/json',
    },
    body: body !== undefined ? JSON.stringify(body) : undefined,
    signal,
  });

  if (!res.ok) {
    throw await parseErrorResponse(res);
  }

  return (await res.json()) as T;
}

export async function apiUpload<T>(path: string, formData: FormData, signal?: AbortSignal): Promise<T> {
  const url = `${API_BASE}${path.startsWith('/') ? path : `/${path}`}`;
  const res = await fetch(url, {
    method: 'POST',
    headers: {
      'Accept': 'application/json',
    },
    body: formData,
    signal,
  });

  if (!res.ok) {
    throw await parseErrorResponse(res);
  }

  return (await res.json()) as T;
}

export async function apiDelete(path: string, signal?: AbortSignal): Promise<void> {
  const url = `${API_BASE}${path.startsWith('/') ? path : `/${path}`}`;
  const res = await fetch(url, {
    method: 'DELETE',
    headers: {
      'Accept': 'application/json',
    },
    signal,
  });

  if (!res.ok) {
    throw await parseErrorResponse(res);
  }
}
