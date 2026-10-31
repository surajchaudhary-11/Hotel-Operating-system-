const API_BASE = "/api/v1";

export interface ApiOptions extends RequestInit {
  hotelId?: string;
}

export async function apiFetch<T>(
  endpoint: string,
  options: ApiOptions = {}
): Promise<T> {
  const token = typeof window !== "undefined" ? localStorage.getItem("hotelos_token") : null;
  const activeHotelId = options.hotelId || (typeof window !== "undefined" ? localStorage.getItem("hotelos_active_hotel_id") : null);

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

  // Handle file downloads / binary response
  const contentType = response.headers.get("content-type");
  if (contentType && (contentType.includes("application/pdf") || contentType.includes("image/"))) {
    return response.blob() as unknown as T;
  }

  return response.json() as Promise<T>;
}

