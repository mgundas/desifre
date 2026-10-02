import { T } from '../i18n/tr.js';

export class ApiError extends Error {
  constructor(message, status) { super(message); this.status = status; }
}

async function request(method, path, body) {
  let res;
  try {
    res = await fetch(path, {
      method,
      headers: body !== undefined ? { 'Content-Type': 'application/json' } : {},
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
  } catch {
    throw new ApiError(T.common.networkError, 0);
  }
  if (!res.ok) {
    let msg = T.errors.generic;
    try {
      const j = await res.json();
      if (typeof j.detail === 'string') msg = j.detail;
    } catch { /* gövde JSON değil */ }
    throw new ApiError(msg, res.status);
  }
  return res.json();
}

export const api = {
  get: (p) => request('GET', p),
  put: (p, b) => request('PUT', p, b ?? {}),
  post: (p, b) => request('POST', p, b ?? {}),
  del: (p) => request('DELETE', p),

  /** Dosyayı ham gövde olarak yükler ve ilerlemeyi bildirir. */
  upload(file, options, onProgress) {
    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      const q = `filename=${encodeURIComponent(file.name)}&options=${encodeURIComponent(JSON.stringify(options))}`;
      xhr.open('POST', `/api/jobs?${q}`);
      xhr.upload.onprogress = (e) => { if (e.lengthComputable) onProgress?.(e.loaded / e.total); };
      xhr.onerror = () => reject(new ApiError(T.common.networkError, 0));
      xhr.onload = () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          try { resolve(JSON.parse(xhr.responseText)); } catch { reject(new ApiError(T.errors.generic, xhr.status)); }
          return;
        }
        let msg = T.errors.generic;
        try { const j = JSON.parse(xhr.responseText); if (typeof j.detail === 'string') msg = j.detail; } catch { /* yoksay */ }
        reject(new ApiError(msg, xhr.status));
      };
      xhr.send(file);
    });
  },
};
