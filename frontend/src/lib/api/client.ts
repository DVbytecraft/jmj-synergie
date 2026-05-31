/**
 * Axios instance — auto-attaches JWT Bearer token, handles silent token refresh.
 *
 * Refresh flow:
 *   On 401, performRefresh() is called. It is a singleton: if a refresh is already
 *   in-flight (e.g. React StrictMode double-invoke, or concurrent 401 responses),
 *   all callers await the same promise instead of each making their own request.
 *   This prevents JTI-rotation conflicts where the 2nd refresh call would fail
 *   because the first one already rotated the token.
 */
import axios, { AxiosInstance, InternalAxiosRequestConfig } from "axios";
import { useAuthStore } from "@/store/auth.store";

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
