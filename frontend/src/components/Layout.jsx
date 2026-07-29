import React from "react";
import { useNavigate, Link } from "react-router-dom";
import { ChevronLeft, LogOut, Pencil, Check, Save, Loader2 } from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { useContent } from "@/context/ContentContext";

export default function Layout({ title, subtitle, showBack = true, children, testId }) {
  const navigate = useNavigate();
  const { isAdmin, logout } = useAuth();
  const { editMode, setEditMode, dirty, saving, save, reload } = useContent();

  const handleLogout = async () => {
    await logout();
    navigate("/login", { replace: true });
  };

  const toggleEdit = async () => {
    if (editMode && dirty) {
      await save();
    }
    if (editMode) {
      await reload();
    }
    setEditMode(!editMode);
  };

  return (
    <div className="min-h-screen bg-slate-50 font-body" data-testid={testId}>
      <header className="bg-slate-900 text-white">
        <div className="max-w-5xl mx-auto px-4 sm:px-6 py-4 flex items-center justify-between gap-3">
          <div className="min-w-0">
            <div className="font-heading font-bold text-lg sm:text-xl truncate">Fisher Family Portal</div>
          </div>
          <div className="flex items-center gap-2">
            {isAdmin && (
              <button
                data-testid="edit-mode-toggle"
                onClick={toggleEdit}
                className="inline-flex items-center gap-2 rounded-lg px-3 py-2 min-h-[44px] font-semibold bg-white text-slate-900 hover:bg-slate-100 transition-colors"
              >
                {saving ? (
                  <Loader2 className="w-5 h-5 animate-spin" />
                ) : editMode ? (
                  <Check className="w-5 h-5" />
                ) : (
                  <Pencil className="w-5 h-5" />
                )}
                <span className="hidden sm:inline">{editMode ? "Done" : "Edit"}</span>
              </button>
            )}
            {isAdmin && editMode && dirty && (
              <button
                data-testid="save-changes-btn"
                onClick={save}
                className="inline-flex items-center gap-2 rounded-lg px-3 py-2 min-h-[44px] font-semibold bg-blue-600 text-white hover:bg-blue-500 transition-colors"
              >
                <Save className="w-5 h-5" />
                <span className="hidden sm:inline">Save</span>
              </button>
            )}
            <button
              data-testid="logout-btn"
              onClick={handleLogout}
              className="inline-flex items-center gap-2 rounded-lg px-3 py-2 min-h-[44px] font-semibold border border-slate-600 text-white hover:bg-slate-800 transition-colors"
            >
              <LogOut className="w-5 h-5" />
              <span className="hidden sm:inline">Log Out</span>
            </button>
          </div>
        </div>
      </header>

      {isAdmin && editMode && (
        <div className="bg-blue-100 border-b-2 border-blue-300 text-blue-900 text-center py-2 text-base font-semibold" data-testid="edit-mode-banner">
          Edit mode is on — update any field, then press Save.
        </div>
      )}

      <main className="max-w-5xl mx-auto px-4 sm:px-6 py-6 sm:py-10">
        {showBack && (
          <Link
            to="/dashboard"
            data-testid="back-to-dashboard"
            className="inline-flex items-center gap-1 text-blue-900 font-semibold mb-5 hover:underline"
          >
            <ChevronLeft className="w-5 h-5" />
            Back to Dashboard
          </Link>
        )}
        <div className="mb-8">
          <h1 className="font-heading text-3xl sm:text-4xl font-bold text-slate-950 tracking-tight">{title}</h1>
          {subtitle && <p className="mt-2 text-lg sm:text-xl text-slate-700 leading-relaxed">{subtitle}</p>}
        </div>
        {children}
      </main>
    </div>
  );
}

export function SectionCard({ title, children, testId }) {
  return (
    <section className="bg-white border border-slate-200 rounded-xl p-6 shadow-sm mb-6" data-testid={testId}>
      {title && <h2 className="font-heading text-2xl font-semibold text-slate-900 mb-4">{title}</h2>}
      {children}
    </section>
  );
}
