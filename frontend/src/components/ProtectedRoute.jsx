import React from "react";
import { useNavigate, Navigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";

export default function ProtectedRoute({ children, allowedRoles }) {
  const { auth } = useAuth();
  const navigate = useNavigate();

  React.useEffect(() => {
    if (auth === false) navigate("/login", { replace: true });
  }, [auth, navigate]);

  if (auth === null) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50">
        <p className="text-lg text-slate-600" data-testid="loading-state">
          Loading…
        </p>
      </div>
    );
  }
  if (auth === false) return null;
  if (allowedRoles && !allowedRoles.includes(auth.role)) return <Navigate to="/dashboard" replace />;
  return children;
}
