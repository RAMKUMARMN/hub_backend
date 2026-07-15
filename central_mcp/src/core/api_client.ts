import axios, { AxiosRequestConfig } from 'axios';
import FormData from 'form-data';
import * as fs from 'fs';
import * as path from 'path';

export type HttpMethod = 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';

export interface BackendRequest {
  baseUrl: string;
  token?: string;
  body?: unknown;
  query?: Record<string, unknown>;
  headers?: Record<string, string>;
  responseType?: AxiosRequestConfig['responseType'];
}

function cleanToken(token?: string): string | undefined {
  const value = token?.trim().replace(/^Bearer\s+/i, '');
  return value || undefined;
}

function backendError(error: any): Error {
  const data = error.response?.data;
  const detail = data?.detail ?? data?.message ?? data ?? error.message;
  const message = typeof detail === 'string' ? detail : JSON.stringify(detail);
  const status = error.response?.status;
  return new Error(status ? `Backend ${status}: ${message}` : message);
}

export async function forwardToBackend(
  method: HttpMethod,
  endpoint: string,
  options: BackendRequest
): Promise<any> {
  const url = `${options.baseUrl.replace(/\/$/, '')}${endpoint}`;
  const token = cleanToken(options.token);
  const headers: Record<string, string> = {
    Accept: 'application/json',
    ...options.headers,
  };

  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }
  const hasContentType = Object.keys(headers)
    .some(name => name.toLowerCase() === 'content-type');
  if (options.body !== undefined && !hasContentType) {
    headers['Content-Type'] = 'application/json';
  }

  console.error(`[SmartHub MCP] ${method} ${url}`);

  try {
    const response = await axios({
      method,
      url,
      headers,
      data: options.body,
      params: options.query,
      responseType: options.responseType,
      timeout: Number(process.env.BACKEND_TIMEOUT_MS || 120000),
      validateStatus: status => status >= 200 && status < 300,
    });

    if (response.status === 204 || response.data === '') {
      return { success: true, status: response.status };
    }
    if (String(response.headers['content-type'] || '').includes('text/event-stream')) {
      return parseServerSentEvents(String(response.data));
    }
    return response.data;
  } catch (error: any) {
    throw backendError(error);
  }
}

export async function uploadFileToBackend(
  endpoint: string,
  filePath: string,
  options: Omit<BackendRequest, 'body' | 'headers'>
): Promise<any> {
  const absolutePath = path.resolve(filePath);
  if (!fs.existsSync(absolutePath) || !fs.statSync(absolutePath).isFile()) {
    throw new Error(`File not found: ${absolutePath}`);
  }

  const form = new FormData();
  form.append('file', fs.createReadStream(absolutePath), path.basename(absolutePath));

  return forwardToBackend('POST', endpoint, {
    ...options,
    body: form,
    headers: form.getHeaders(),
  });
}

function parseServerSentEvents(raw: string): Record<string, unknown> {
  const chunks: string[] = [];
  const events: unknown[] = [];

  for (const line of raw.split(/\r?\n/)) {
    if (!line.startsWith('data:')) {
      continue;
    }
    const value = line.slice(5).trim();
    if (!value || value === '[DONE]') {
      continue;
    }
    try {
      const event = JSON.parse(value);
      events.push(event);
      if (typeof event?.delta === 'string') {
        chunks.push(event.delta);
      } else if (typeof event?.content === 'string') {
        chunks.push(event.content);
      } else if (typeof event?.message === 'string') {
        chunks.push(event.message);
      }
    } catch {
      chunks.push(value);
    }
  }

  return {
    response: chunks.join(''),
    events,
  };
}
