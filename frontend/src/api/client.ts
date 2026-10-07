import createClient, { type Middleware } from "openapi-fetch";

import { ApiError } from "../lib/errors";
import { authStore } from "./authStore";
import type { paths } from "./schema";

export const API_BASE: string = import.meta.env.VITE_API_BASE_URL ?? "";

const auth: Middleware = {
  onRequest({ request }) {
    const token = authStore.getToken();
    if (token) request.headers.set("Authorization", `Bearer ${token}`);
    return request;
  },
  onResponse({ response }) {
    if (response.status === 401) authStore.expire();
    return response;
  },
};

export const api = createClient<paths>({ baseUrl: API_BASE });
api.use(auth);

/** Restituisce i dati oppure solleva un ApiError con il messaggio dell'API. */
export function unwrap<T>(result: { data?: T; error?: unknown; response: Response }): T {
  if (result.error !== undefined || result.data === undefined) {
    throw new ApiError(result.response.status, result.error);
  }
  return result.data;
}
