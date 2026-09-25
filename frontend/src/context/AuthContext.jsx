import React, { createContext, useContext, useEffect, useState, useCallback } from "react";
import { api } from "@/lib/api";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [auth, setAuth] = useState(null); // null=checking, false=logged out, {role} = logged in

  const check = useCallback(async () => {
    try {
      const { data } = await api.get("/auth/me");
      setAuth(data);
      // Phase 0: auto-detect timezone from browser on first login
      if (data && !data.timezone_confirmed) {
        const detected = Intl.DateTimeFormat().resolvedOptions().timeZone;
        if (detected && detected !== data.timezone) {
          try {
            await api.patch("/auth/timezone", { timezone: detected, confirm: false });
          } catch (err) {
            console.error("Timezone auto-detect failed:", err);
          }
        }
      }
    } catch {
      setAuth(false);
    }
  }, []);

  useEffect(() => {
    check();
  }, [check]);

  const logout = useCallback(async () => {
    try {
      await api.post("/auth/logout");
    } catch (err) {
      console.error("Logout request failed:", err);
    }
    setAuth(false);
  }, []);

  const value = {
    auth,
    isAuthed: !!auth && auth !== false,
    isAdmin: !!auth && auth.role === "admin",
    setAuth,
    logout,
    refresh: check,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  return useContext(AuthContext);
}
