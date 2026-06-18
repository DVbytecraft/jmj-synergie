/**
 * Axios instance — auto-attaches JWT Bearer token, handles silent token refresh.
 *
 * Refresh flow:
 *   On 401, performRefresh() is called. It is a singleton: if a refresh is already
 *   in-flight (e.g. React StrictMode double-invoke, or concurrent 401 responses),
 *   all callers await the same promise instead of each making their own request.
 *   This prevents JTI-rotation conflicts where the 2nd refresh call would fail
 *   because the first one already rotated the token.
 *
 * 502/503/504 retry:
 *   On Render.com free tier, the backend spins down after inactivity and takes
 *   ~30-60s to cold-start. Requests during this window get 502 from the proxy.
 *   We retry up to 2 times with exponential backoff (2s, 4s) so the user doesn't
 *   have to manually refresh the page.
 */
import axios, { AxiosInstance, InternalAxiosRequestConfig } from "axios";
import { useAuthStore } from "@/store/auth.store";

const GATEWAY_ERRORS = new Set([502, 503, 504]);
const MAX_RETRIES = 2;
const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

// Always use a relative path so the browser never bypasses the Next.js proxy.
// NEXT_PUBLIC_API_URL in Render's dashboard can accidentally be set to the
// absolute backend URL, which breaks CSP and same-origin assumptions.
const BASE_URL = "/api/v1";

export const apiClient: AxiosInstance = axios.create({
  baseURL: BASE_URL,
  timeout: 30_000,
  headers: { "Content-Type": "application/json" },
  withCredentials: true,
});

// ─── Singleton refresh — one in-flight request shared by all callers ──────────
let _refreshPromise: Promise<string> | null = null;

/**
 * Attempt a silent token refresh using the HttpOnly 'rt' cookie.
 * Returns the new access token, or throws on failure.
 * Concurrent calls share the same in-flight request.
 */
export async function performRefresh(): Promise<string> {
  if (_refreshPromise) return _refreshPromise;

  _refreshPromise = axios
    .post(`${BASE_URL}/auth/refresh`, {}, { withCredentials: true })
    .then((res) => {
      const token: string = res.data.access_token;
      useAuthStore.getState().setAuth(token);
      return token;
    })
    .finally(() => {
      _refreshPromise = null;
    });

  return _refreshPromise;
}

// ─── Request interceptor — attach Bearer token ────────────────────────────────
apiClient.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const token = useAuthStore.getState().accessToken;
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// ─── Response interceptor — silent refresh on 401 ────────────────────────────
let failedQueue: Array<{ resolve: (token: string) => void; reject: (err: unknown) => void }> = [];

const processQueue = (error: unknown, token: string | null) => {
  failedQueue.forEach(({ resolve, reject }) => (error ? reject(error) : resolve(token!)));
  failedQueue = [];
};

apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;

    // Retry on gateway errors (Render.com cold start)
    if (GATEWAY_ERRORS.has(error.response?.status)) {
      const retries: number = originalRequest._retryCount ?? 0;
      if (retries < MAX_RETRIES) {
        originalRequest._retryCount = retries + 1;
        await sleep(2000 * (retries + 1));
        return apiClient(originalRequest);
      }
    }

    if (error.response?.status !== 401 || originalRequest._retry) {
      return Promise.reject(error);
    }

    originalRequest._retry = true;

    // If a refresh is already in-flight, queue this request
    if (_refreshPromise) {
      return new Promise((resolve, reject) => {
        failedQueue.push({ resolve, reject });
      }).then((token) => {
        originalRequest.headers.Authorization = `Bearer ${token}`;
        return apiClient(originalRequest);
      });
    }

    try {
      const newToken = await performRefresh();
      apiClient.defaults.headers.common.Authorization = `Bearer ${newToken}`;
      processQueue(null, newToken);
      originalRequest.headers.Authorization = `Bearer ${newToken}`;
      return apiClient(originalRequest);
    } catch (refreshError) {
      processQueue(refreshError, null);
      useAuthStore.getState().clearAuth();
      return Promise.reject(refreshError);
    }
  }
);
