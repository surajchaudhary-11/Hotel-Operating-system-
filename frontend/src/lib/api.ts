const API_BASE = "/api/v1";

export interface ApiOptions extends RequestInit {
  hotelId?: string;
  useCache?: boolean;
  cacheTtlMs?: number;
}

// In-memory request deduplication map to prevent redundant concurrent fetches
const inFlightRequests = new Map<string, Promise<any>>();

// In-memory client cache with TTL and tenant isolation
interface CacheEntry {
  data: any;
  timestamp: number;
  expiry: number;
}
const apiCache = new Map<string, CacheEntry>();

export function getCacheKey(endpoint: string, hotelId: string | null): string {
  return `${hotelId || "global"}:${endpoint}`;
}

export function invalidateApiCache(prefix?: string) {
  if (!prefix) {
    apiCache.clear();
    return;
  }
  const keysToDelete: string[] = [];
  apiCache.forEach((_, key) => {
    if (key.includes(prefix)) {
      keysToDelete.push(key);
    }
  });
  keysToDelete.forEach((key) => apiCache.delete(key));
}

export async function apiFetch<T>(
  endpoint: string,
  options: ApiOptions = {}
): Promise<T> {
  const method = (options.method || "GET").toUpperCase();
  const token = typeof window !== "undefined" ? localStorage.getItem("hotelos_token") : null;
  const activeHotelId = options.hotelId || (typeof window !== "undefined" ? localStorage.getItem("hotelos_active_hotel_id") : null);

  const cacheKey = getCacheKey(endpoint, activeHotelId);

  // Invalidate cache on mutations
  if (method !== "GET") {
    invalidateApiCache();
  }

  // Check cache for GET requests if caching is enabled
  if (method === "GET" && options.useCache) {
    const cached = apiCache.get(cacheKey);
    const now = Date.now();
    if (cached && cached.expiry > now) {
      return cached.data as T;
    }
  }

  // Deduplicate identical in-flight GET requests
  if (method === "GET") {
    const inFlight = inFlightRequests.get(cacheKey);
    if (inFlight) {
      return inFlight as Promise<T>;
    }
  }

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };

  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  if (activeHotelId) {
    headers["X-Hotel-ID"] = activeHotelId;
  }

  const url = endpoint.startsWith("http") ? endpoint : `${API_BASE}${endpoint}`;

  const fetchPromise = (async () => {
    try {
      const response = await fetch(url, {
        ...options,
        headers,
      });

      if (!response.ok) {
        let errorDetail = "An unexpected error occurred";
        try {
          const errJson = await response.json();
          errorDetail = errJson.detail || errJson.message || errorDetail;
        } catch {
          errorDetail = response.statusText || errorDetail;
        }
        throw new Error(errorDetail);
      }

      const contentType = response.headers.get("content-type");
      if (contentType && (contentType.includes("application/pdf") || contentType.includes("image/"))) {
        return (await response.blob()) as unknown as T;
      }

      const data = (await response.json()) as T;

      // Save to cache if caching requested or for safe idempotent GETs
      if (method === "GET" && options.useCache) {
        const ttl = options.cacheTtlMs ?? 30000; // default 30s TTL
        apiCache.set(cacheKey, {
          data,
          timestamp: Date.now(),
          expiry: Date.now() + ttl,
        });
      }

      return data;
    } finally {
      if (method === "GET") {
        inFlightRequests.delete(cacheKey);
      }
    }
  })();

  if (method === "GET") {
    inFlightRequests.set(cacheKey, fetchPromise);
  }

  return fetchPromise;
}

/**
 * Fast cached fetch with automatic background revalidation (Stale-While-Revalidate)
 */
export async function apiFetchCached<T>(
  endpoint: string,
  optionsOrTtl: ApiOptions | number = {},
  ttlMs = 45000
): Promise<T> {
  const opts: ApiOptions = typeof optionsOrTtl === "number" ? {} : (optionsOrTtl || {});
  const ttl: number = typeof optionsOrTtl === "number" ? optionsOrTtl : ttlMs;
  return apiFetch<T>(endpoint, {
    ...opts,
    useCache: true,
    cacheTtlMs: ttl,
  });
}
