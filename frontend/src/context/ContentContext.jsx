import React, { createContext, useContext, useEffect, useState, useCallback } from "react";
import { cloneDeep, get, set } from "lodash";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";

const ContentContext = createContext(null);

export function ContentProvider({ children }) {
  const { isAuthed, isAdmin } = useAuth();
  const [content, setContent] = useState(null);
  const [editMode, setEditModeState] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    if (!isAuthed) return;
    try {
      const { data } = await api.get("/content");
      setContent(data);
      setDirty(false);
    } catch (err) {
      console.error("Content load failed:", err);
      /* auth failures are handled by the protected route */
    }
  }, [isAuthed]);

  useEffect(() => {
    load();
  }, [load]);

  const setEditMode = (v) => {
    if (!isAdmin) return;
    setEditModeState(v);
  };

  const update = (path, value) => {
    setContent((prev) => {
      const next = cloneDeep(prev);
      set(next, path, value);
      return next;
    });
    setDirty(true);
  };

  const addItem = (path, item) => {
    setContent((prev) => {
      const next = cloneDeep(prev);
      const arr = get(next, path) || [];
      arr.push(item);
      set(next, path, arr);
      return next;
    });
    setDirty(true);
  };

  const removeItem = (path, index) => {
    setContent((prev) => {
      const next = cloneDeep(prev);
      const arr = (get(next, path) || []).slice();
      arr.splice(index, 1);
      set(next, path, arr);
      return next;
    });
    setDirty(true);
  };

  const save = async () => {
    setSaving(true);
    try {
      await api.put("/content", { content });
      setDirty(false);
      toast.success("Changes saved");
    } catch {
      toast.error("Could not save changes");
    } finally {
      setSaving(false);
    }
  };

  const value = {
    content,
    editMode,
    setEditMode,
    dirty,
    saving,
    update,
    addItem,
    removeItem,
    save,
    reload: load,
  };

  return <ContentContext.Provider value={value}>{children}</ContentContext.Provider>;
}

export function useContent() {
  return useContext(ContentContext);
}

export const newId = () =>
  (window.crypto && window.crypto.randomUUID
    ? window.crypto.randomUUID()
    : "id-" + Math.random().toString(36).slice(2));
