import { useState, useCallback, useRef, useEffect } from "react";

const API_BASE =
  import.meta.env.VITE_API_URL ||
  "http://127.0.0.1:5000/api";

const STORAGE_KEY = "cinema_access_token";

// localStorage can be unavailable (private mode, blocked cookies), so every
// access is wrapped in try/catch and the app still works without it.
function readStoredToken() {
  try {
    return window.localStorage.getItem(STORAGE_KEY);
  } catch {
    return null;
  }
}

function writeStoredToken(token) {
  try {
    if (token) window.localStorage.setItem(STORAGE_KEY, token);
    else window.localStorage.removeItem(STORAGE_KEY);
  } catch {
    /* ignore */
  }
}

// Send a request to Flask. Throws an Error with .status set on failure.
async function request(endpoint, options = {}) {
  const response = await fetch(`${API_BASE}${endpoint}`, {
    ...options,
    headers: {
      ...(options.body ? { "Content-Type": "application/json" } : {}),
      ...options.headers,
    },
  });

  const data = await response.json().catch(() => ({}));

  if (!response.ok) {
    const error = new Error(
      data.error || `Request failed (${response.status})`
    );
    error.status = response.status;
    throw error;
  }

  return data;
}

export default function useAuth() {
  const [accessToken, setAccessToken] = useState(null);
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(false);
  // True while a saved token is being re-checked on page load.
  const [initializing, setInitializing] = useState(() =>
    Boolean(readStoredToken())
  );
  const [error, setError] = useState(null);

  // Prevent older requests from overwriting newer auth state.
  const requestId = useRef(0);
  const mounted = useRef(true);

  // Restore a saved session when the page loads or refreshes.
  useEffect(() => {
    mounted.current = true;
    const stored = readStoredToken();

    if (stored) {
      const id = ++requestId.current;

      request("/auth/me", {
        headers: { Authorization: `Bearer ${stored}` },
      })
        .then((data) => {
          if (!mounted.current || id !== requestId.current) return;
          if (data.user) {
            setAccessToken(stored);
            setUser(data.user);
          } else {
            writeStoredToken(null);
          }
        })
        .catch(() => {
          // Expired, invalid, or the backend is down: start logged out.
          if (id === requestId.current) writeStoredToken(null);
        })
        .finally(() => {
          if (mounted.current) setInitializing(false);
        });
    }

    return () => {
      mounted.current = false;
      requestId.current += 1;
    };
  }, []);

  // End the session (client side; tokens are stateless on the server).
  const logout = useCallback(() => {
    requestId.current += 1;
    writeStoredToken(null);
    setAccessToken(null);
    setUser(null);
    setError(null);
    setLoading(false);
    setInitializing(false);
  }, []);

  // Log in with email and password. Returns the user, or throws.
  const login = useCallback(async (email, password) => {
    const id = ++requestId.current;

    setLoading(true);
    setError(null);
    setAccessToken(null);
    setUser(null);

    try {
      const data = await request("/auth/login", {
        method: "POST",
        body: JSON.stringify({ email, password }),
      });

      if (!data.access_token || typeof data.access_token !== "string") {
        throw new Error("Login response did not include an access token.");
      }

      // Confirm identity using the protected endpoint.
      const verified = await request("/auth/me", {
        headers: { Authorization: `Bearer ${data.access_token}` },
      });

      if (!verified.user) {
        throw new Error("Unable to retrieve authenticated user.");
      }

      if (mounted.current && id === requestId.current) {
        writeStoredToken(data.access_token);
        setAccessToken(data.access_token);
        setUser(verified.user);
        setInitializing(false);
      }

      return verified.user;
    } catch (err) {
      if (mounted.current && id === requestId.current) {
        setError(err.message || "Login failed.");
      }
      throw err;
    } finally {
      if (mounted.current && id === requestId.current) {
        setLoading(false);
      }
    }
  }, []);

  // Validate an access token supplied by another login flow.
  const signIn = useCallback(async (token) => {
    const id = ++requestId.current;

    setLoading(true);
    setError(null);
    setAccessToken(null);
    setUser(null);

    try {
      if (typeof token !== "string" || !token.trim()) {
        throw new Error("A valid access token is required.");
      }

      const data = await request("/auth/me", {
        headers: { Authorization: `Bearer ${token}` },
      });

      if (!data.user) {
        throw new Error("Authenticated user not found.");
      }

      if (mounted.current && id === requestId.current) {
        writeStoredToken(token);
        setAccessToken(token);
        setUser(data.user);
        setInitializing(false);
      }

      return data.user;
    } catch (err) {
      if (mounted.current && id === requestId.current) {
        setError(err.message || "Authentication failed.");
      }
      throw err;
    } finally {
      if (mounted.current && id === requestId.current) {
        setLoading(false);
      }
    }
  }, []);

  // Call a protected endpoint with the Bearer token attached.
  // A 401 means the session is gone, so the user is logged out.
  const authFetch = useCallback(
    async (endpoint, options = {}) => {
      try {
        return await request(endpoint, {
          ...options,
          headers: {
            ...options.headers,
            ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
          },
        });
      } catch (err) {
        if (err.status === 401) logout();
        throw err;
      }
    },
    [accessToken, logout]
  );

  // Reload the current user (use after favorites or profile changes).
  const refreshUser = useCallback(async () => {
    if (!accessToken) return null;

    const id = requestId.current;
    const data = await authFetch("/auth/me");

    if (mounted.current && id === requestId.current) {
      setUser(data.user);
      setError(null);
    }

    return data.user;
  }, [accessToken, authFetch]);

  return {
    accessToken,
    token: accessToken,
    user,
    isAuthenticated: Boolean(accessToken && user),
    loading,
    initializing,
    error,
    login,
    signIn,
    logout,
    authFetch,
    refreshUser,
  };
}

export { useAuth };
