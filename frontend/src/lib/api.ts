const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

type TokenPair = {
  access_token: string;
  refresh_token: string;
  expires_in: number;
};

// Prevent multiple simultaneous 401 responses from triggering
// multiple refresh requests at the same time.
let refreshPromise: Promise<string | null> | null = null;

function getAccessToken(): string | null {
  if (typeof window === "undefined") {
    return null;
  }

  return localStorage.getItem("access_token");
}

function getRefreshToken(): string | null {
  if (typeof window === "undefined") {
    return null;
  }

  return localStorage.getItem("refresh_token");
}

export function saveTokenPair(tokenPair: TokenPair) {
  if (typeof window === "undefined") {
    return;
  }

  localStorage.setItem("access_token", tokenPair.access_token);
  localStorage.setItem("refresh_token", tokenPair.refresh_token);
}

export function clearTokens() {
  if (typeof window === "undefined") {
    return;
  }

  localStorage.removeItem("access_token");
  localStorage.removeItem("refresh_token");
}

async function refreshAccessToken(): Promise<string | null> {
  const refreshToken = getRefreshToken();

  if (!refreshToken) {
    return null;
  }

  // If another request is already refreshing the token,
  // wait for that same refresh operation.
  if (refreshPromise) {
    return refreshPromise;
  }

  refreshPromise = (async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/auth/refresh`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          refresh_token: refreshToken,
        }),
      });

      if (!response.ok) {
        clearTokens();
        return null;
      }

      const tokenPair: TokenPair = await response.json();

      saveTokenPair(tokenPair);

      return tokenPair.access_token;
    } catch (error) {
      console.error("Token refresh failed:", error);
      clearTokens();
      return null;
    } finally {
      refreshPromise = null;
    }
  })();

  return refreshPromise;
}

export async function apiFetch(
  endpoint: string,
  options: RequestInit = {}
) {
  const makeRequest = async (token: string | null) => {
    const headers = new Headers(options.headers);

    headers.set("Content-Type", "application/json");

    if (token) {
      headers.set("Authorization", `Bearer ${token}`);
    }

    return fetch(`${API_BASE_URL}${endpoint}`, {
      ...options,
      headers,
    });
  };

  let token = getAccessToken();

  let response = await makeRequest(token);

  // Login itself should never trigger an existing-session refresh.
  // A failed login should simply return its normal 401.
  const isAuthenticationEndpoint =
    endpoint === "/auth/login" ||
    endpoint === "/auth/refresh";

  if (
    response.status === 401 &&
    !isAuthenticationEndpoint &&
    getRefreshToken()
  ) {
    token = await refreshAccessToken();

    if (token) {
      response = await makeRequest(token);
    }
  }

  if (!response.ok) {
    throw new Error(`API Error: ${response.status}`);
  }

  return response.json();
}