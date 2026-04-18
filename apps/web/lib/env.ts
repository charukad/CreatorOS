const fallbackApiBaseUrl = "http://localhost:8000";

export const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? fallbackApiBaseUrl;

