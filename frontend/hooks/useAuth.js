import { useState, useCallback, useRef, useEffect } from "react";

const API_BASE =
  import.meta.env.VITE_API_URL ||
  "http://127.0.0.1:5000/api";

export default function useAuth() {
  const [accessToken, setAccessToken] = useState(null);
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // Prevent older requests from overwriting newer auth state.
  const requestId = useRef(0);
  const mounted = useRef(true);

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
      requestId.current += 1;
    };
  }, []);

  // Clear the current authentication session.
  const logout = useCallback(() => {
    requestId.current += 1;
    setAccessToken(null);
    setUser(null);
    setError(null);
    setLoading(false);
  }, []);

  // Send authentication requests to Flask.
  const authRequest = useCallback(async (
    endpoint,
    options = {}
  ) => {
    const response = await fetch(
      `${API_BASE}${endpoint}`,
      {
        ...options,
        headers: {
          ...(options.body
            ? { "Content-Type": "application/json" }
            : {}),
          ...options.headers,
        },
      }
    );

    const data = await response.json().catch(() => ({}));

    if (!response.ok) {
      throw new Error(
        data.error ||
        `Request failed (${response.status})`
      );
    }

    return data;
  }, []);

  // Log in with email and password.
  const login = useCallback(async (email, password) => {
    const id = ++requestId.current;

    setLoading(true);
    setError(null);
    setAccessToken(null);
    setUser(null);

    try {
      const data = await authRequest("/auth/login", {
        method: "POST",
        body: JSON.stringify({
          email,
          password,
        }),
      });

      if (
        !data.access_token ||
        typeof data.access_token !== "string"
      ) {
        throw new Error(
          "Login response did not include an access token."
        );
      }

      // Confirm identity using the protected endpoint.
      const verified = await authRequest("/auth/me", {
        method: "GET",
        headers: {
          Authorization: `Bearer ${data.access_token}`,
        },
      });

      if (!verified.user) {
        throw new Error(
          "Unable to retrieve authenticated user."
        );
      }

      if (mounted.current && id === requestId.current) {
        setAccessToken(data.access_token);
        setUser(verified.user);
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
  }, [authRequest]);

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

      const data = await authRequest("/auth/me", {
        method: "GET",
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      if (!data.user) {
        throw new Error("Authenticated user not found.");
      }

      if (mounted.current && id === requestId.current) {
        setAccessToken(token);
        setUser(data.user);
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
  }, [authRequest]);

  // Reload the current user's profile.
  const refreshUser = useCallback(async () => {
    if (!accessToken) {
      return null;
    }

    const id = requestId.current;

    try {
      const data = await authRequest("/auth/me", {
        method: "GET",
        headers: {
          Authorization: `Bearer ${accessToken}`,
        },
      });

      if (mounted.current && id === requestId.current) {
        setUser(data.user);
        setError(null);
      }

      return data.user;
    } catch (err) {
      if (mounted.current && id === requestId.current) {
        if (err.message.includes("(401)")) {
          logout();
        } else {
          setError(err.message);
        }
      }
      throw err;
    }
  }, [accessToken, authRequest, logout]);

  // Return authentication state and functions.
  return {
    accessToken,
    token: accessToken,
    user,
    isAuthenticated: Boolean(accessToken && user),
    loading,
    error,
    login,
    signIn,
    logout,
    refreshUser,
  };
}

export { useAuth };
