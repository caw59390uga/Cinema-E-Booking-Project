import { useCallback, useState } from "react";

const API_BASE =
  import.meta.env.VITE_API_URL ||
  "http://127.0.0.1:5000/api";

export default function useAuth() {
  const [accessToken, setAccessToken] = useState(null);
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // Clear authentication state
  const logout = useCallback(() => {
    setAccessToken(null);
    setUser(null);
    setError(null);
  }, []);

  // Authenticate using an access token
  const signIn = useCallback(async (token) => {
    if (typeof token !== "string" || !token.trim()) {
      throw new Error("A valid access token is required.");
    }

    setLoading(true);
    setError(null);
    setAccessToken(null);
    setUser(null);

    try {
      const response = await fetch(`${API_BASE}/auth/me`, {
        method: "GET",
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      const data = await response.json().catch(() => ({}));

      if (!response.ok) {
        throw new Error(
          data.error ||
          `Authentication failed (${response.status})`
        );
      }

      if (!data.user) {
        throw new Error(
          "Authentication response did not include a user."
        );
      }

      setUser(data.user);
      setAccessToken(token);

      return data.user;
    } catch (err) {
      setError(
        err.message || "Unable to authenticate."
      );

      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  return {
    accessToken,
    token: accessToken,
    user,
    isAuthenticated: Boolean(accessToken && user),
    loading,
    error,
    signIn,
    logout,
  };
}

export { useAuth };
