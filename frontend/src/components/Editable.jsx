import React, { useRef, useState } from "react";
import { get } from "lodash";
import { Trash2, Plus, Upload, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { useContent } from "@/context/ContentContext";
import { api, formatApiErrorDetail } from "@/lib/api";

export function FileUploadField({ path }) {
  const { content, update } = useContent();
  const inputRef = useRef(null);
  const [uploading, setUploading] = useState(false);
  const current = get(content, path) || "";

  const onFile = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    try {
      const fd = new FormData();
      fd.append("file", file);
      const { data } = await api.post("/files/upload", fd, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      update(path, data.url);
      toast.success(`Uploaded ${data.filename}`);
    } catch (err) {
      toast.error(formatApiErrorDetail(err.response?.data?.detail) || "Upload failed");
    } finally {
      setUploading(false);
      if (inputRef.current) inputRef.current.value = "";
    }
  };

  return (
    <div className="mt-2">
      <input ref={inputRef} type="file" className="hidden" data-testid={`file-input-${path}`} onChange={onFile} />
      <button
        type="button"
        data-testid={`upload-btn-${path}`}
        onClick={() => inputRef.current?.click()}
        disabled={uploading}
        className="inline-flex items-center gap-2 text-blue-900 font-semibold border-2 border-dashed border-blue-400 rounded-lg px-4 py-2 min-h-[44px] hover:bg-blue-50 transition-colors disabled:opacity-60"
      >
        {uploading ? <Loader2 className="w-5 h-5 animate-spin" /> : <Upload className="w-5 h-5" />}
        {uploading ? "Uploading…" : "Upload file"}
      </button>
      {current && !/^#?$/.test(current) && (
        <div className="text-sm text-green-700 mt-1 break-all" data-testid={`file-set-${path}`}>
          File attached ✓
        </div>
      )}
    </div>
  );
}

export function EText({ path, className = "text-lg text-slate-900", placeholder = "—" }) {
  const { content, editMode, update } = useContent();
  const value = get(content, path) ?? "";
  if (!editMode) return <span data-testid={`content-${path}`} className={className}>{value || placeholder}</span>;
  return (
    <input
      aria-label={path.split(".").filter((part) => !/^\d+$/.test(part)).join(" ")}
      data-testid={`edit-${path}`}
      className="editable-input"
      value={value}
      onChange={(e) => update(path, e.target.value)}
    />
  );
}

export function EDate({ path, testId }) {
  const { content, editMode, update } = useContent();
  const value = get(content, path) || "";
  if (!editMode) return null;
  return (
    <input
      type="date"
      data-testid={testId || `edit-${path}`}
      className="editable-input"
      value={value}
      onChange={(e) => update(path, e.target.value)}
    />
  );
}

export function EArea({ path, className = "text-lg leading-relaxed text-slate-800", placeholder = "—", rows = 3 }) {
  const { content, editMode, update } = useContent();
  const value = get(content, path) ?? "";
  if (!editMode) return <p data-testid={`content-${path}`} className={className}>{value || placeholder}</p>;
  return (
    <textarea
      rows={rows}
      data-testid={`edit-${path}`}
      className="editable-area"
      value={value}
      onChange={(e) => update(path, e.target.value)}
    />
  );
}

export function Field({ label, path }) {  return (
    <div>
      <div className="text-sm font-semibold uppercase tracking-wide text-slate-500 mb-1">{label}</div>
      <EText path={path} />
    </div>
  );
}

export function DeleteItemButton({ onClick, testId = "delete-item-btn", label = "Remove" }) {
  const { editMode } = useContent();
  if (!editMode) return null;
  return (
    <button
      type="button"
      aria-label={label || "Remove item"}
      data-testid={testId}
      onClick={onClick}
      className="inline-flex items-center gap-2 text-red-700 font-semibold border-2 border-red-300 rounded-lg px-3 py-2 min-h-[44px] hover:bg-red-50 transition-colors"
    >
      <Trash2 className="w-4 h-4" />
      {label}
    </button>
  );
}

export function AddItemButton({ onClick, testId = "add-item-btn", label = "Add Item" }) {
  const { editMode } = useContent();
  if (!editMode) return null;
  return (
    <button
      type="button"
      data-testid={testId}
      onClick={onClick}
      className="inline-flex items-center gap-2 text-blue-900 font-bold border-2 border-blue-900 rounded-lg px-4 py-3 min-h-[52px] hover:bg-blue-50 transition-colors"
    >
      <Plus className="w-5 h-5" />
      {label}
    </button>
  );
}

// External link button whose href is stored in content at `path`.
export function LinkButton({ label, path, icon: Icon, variant = "primary", testId }) {
  const { content, editMode, update } = useContent();
  const href = get(content, path) || "#";
  const base =
    "w-full sm:w-auto min-h-[56px] px-6 text-lg font-bold rounded-lg inline-flex items-center justify-center gap-2 transition-colors focus:ring-4 focus:ring-blue-300 focus:outline-none";
  const styles =
    variant === "primary"
      ? "bg-blue-900 text-white hover:bg-blue-800 shadow-sm"
      : "bg-white text-blue-900 border-2 border-blue-900 hover:bg-slate-50";
  return (
    <div className="w-full sm:w-auto">
      <a href={href} target="_blank" rel="noreferrer" data-testid={testId} className={`${base} ${styles}`}>
        {Icon ? <Icon className="w-5 h-5" /> : null}
        {label}
      </a>
      {editMode && (
        <>
          <input
            data-testid={`edit-${path}`}
            className="editable-input mt-2"
            value={get(content, path) || ""}
            placeholder="Paste secure link (or upload a file below)"
            onChange={(e) => update(path, e.target.value)}
          />
          <FileUploadField path={path} />
        </>
      )}
    </div>
  );
}
