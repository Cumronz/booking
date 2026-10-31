const TOKEN_KEY = "bookshare_token";

export type Query = Record<string, string | number | boolean | null | undefined>;
export type FieldErrors = Record<string, string[]>;

export class ApiError extends Error {
  status: number;
  errors: FieldErrors;
  constructor(status: number, message: string, errors: FieldErrors = {}) {
    super(message);
    this.status = status;
    this.errors = errors;
  }
}

let token: string | null = localStorage.getItem(TOKEN_KEY);
let onUnauthorized: (() => void) | null = null;

export function setToken(value: string | null) {
  token = value;
  if (value) localStorage.setItem(TOKEN_KEY, value);
  else localStorage.removeItem(TOKEN_KEY);
}
export const hasToken = () => token !== null;
export function setUnauthorizedHandler(fn: (() => void) | null) { onUnauthorized = fn; }

interface Options { method?: string; body?: unknown; form?: FormData; query?: Query }

export async function api<T = void>(path: string, opts: Options = {}): Promise<T> {
  const { method = "GET", body, form, query } = opts;
  const url = new URL(`/api${path}`, window.location.origin);
  if (query) {
    for (const [k, v] of Object.entries(query)) {
      if (v !== undefined && v !== null && v !== "") url.searchParams.set(k, String(v));
    }
  }
  const headers: Record<string, string> = {};
  if (token) headers.Authorization = `Token ${token}`;
  let payload: BodyInit | undefined;
  if (form) payload = form;
  else if (body !== undefined) {
    headers["Content-Type"] = "application/json";
    payload = JSON.stringify(body);
  }

  let res: Response;
  try {
    res = await fetch(url, { method, headers, body: payload });
  } catch {
    throw new ApiError(0, "Нет связи с сервером. Проверьте, что backend запущен.");
  }
  if (res.status === 204) return undefined as T;
  const data = await res.json().catch(() => null);
  if (!res.ok) {
    if (res.status === 401 && token && onUnauthorized) onUnauthorized();
    throw new ApiError(res.status, data?.detail ?? "Что-то пошло не так.", data?.errors ?? {});
  }
  return data as T;
}

export function fieldError(err: unknown, field: string): string | undefined {
  if (err instanceof ApiError) return err.errors[field]?.[0];
  return undefined;
}
export function errorText(err: unknown): string {
  if (err instanceof ApiError) {
    const general = err.errors.non_field_errors?.[0];
    return general ?? err.message;
  }
  return "Неизвестная ошибка.";
}
