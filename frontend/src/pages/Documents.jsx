import React, { useState } from "react";
import { FileText, Info, Lock, Search } from "lucide-react";
import Layout, { SectionCard } from "@/components/Layout";
import { useContent, newId } from "@/context/ContentContext";
import { useAuth } from "@/context/AuthContext";
import { EText, EArea, LinkButton, AddItemButton, DeleteItemButton } from "@/components/Editable";

const CATEGORIES = ["Reunion", "Family Business", "Meetings", "Financial", "Legal and Governance", "Forms"];
const ACCESS = ["All Members", "Business Members", "Committee Members", "Restricted"];
const ROLE_LEVEL = { member: 1, business_member: 2, committee_member: 3, admin: 4 };
const ACCESS_LEVEL = { "All Members": 1, "Business Members": 2, "Committee Members": 3, Restricted: 4 };
const canOpen = (role, access) => (ROLE_LEVEL[role] || 1) >= (ACCESS_LEVEL[access] || 1);

function accessBadge(level) {
  const styles = {
    "All Members": "bg-green-100 text-green-800 border-green-300",
    "Business Members": "bg-blue-100 text-blue-800 border-blue-300",
    "Committee Members": "bg-purple-100 text-purple-800 border-purple-300",
    Restricted: "bg-red-100 text-red-800 border-red-300",
  };
  return styles[level] || "bg-slate-100 text-slate-700 border-slate-300";
}

export default function Documents() {
  const { content, editMode, update, addItem, removeItem } = useContent();
  const { auth } = useAuth();
  const [filter, setFilter] = useState("All");
  const [search, setSearch] = useState("");
  if (!content) return null;
  const docs = content.documents || [];
  const matches = (d) => (filter === "All" || d.category === filter) && `${d.title || ""} ${d.description || ""}`.toLowerCase().includes(search.trim().toLowerCase());
  const visibleCount = docs.filter(matches).length;

  return (
    <Layout title="Documents" subtitle="Shared document library for authorized family members." testId="documents-page">
      <div className="bg-slate-100 border border-slate-200 rounded-xl p-5 mb-6 flex items-start gap-3" data-testid="documents-notice">
        <Info className="w-6 h-6 text-blue-900 flex-shrink-0 mt-0.5" />
        <p className="text-base text-slate-700 leading-relaxed">
          Some documents may be stored in a separate secure document system and may require additional permission.
        </p>
      </div>

      <div className="documents-toolbar">
        <span className="documents-total" data-testid="documents-result-count">{visibleCount} document{visibleCount !== 1 ? "s" : ""} in your library</span>
        <label className="document-search"><Search size={17} /><input type="search" aria-label="Search documents" placeholder="Find a document…" data-testid="documents-search" value={search} onChange={(e) => setSearch(e.target.value)} /></label>
      </div>
      <div className="document-filters">
        {["All", ...CATEGORIES].map((c) => (
          <button
            key={c}
            data-testid={`doc-filter-${c.replace(/\s+/g, "-").toLowerCase()}`}
            onClick={() => setFilter(c)}
            aria-pressed={filter === c}
            className={`px-4 py-2 min-h-[44px] rounded-lg font-semibold border-2 transition-colors ${
              filter === c ? "bg-blue-900 text-white border-blue-900" : "bg-white text-blue-900 border-blue-200 hover:border-blue-900"
            }`}
          >
            {c}
          </button>
        ))}
      </div>

      <SectionCard testId="documents-list">
        <div className="grid gap-5 md:grid-cols-2 auto-rows-fr">
          {docs.map((d, i) => {
            if (!matches(d)) return null;
            return (
              <div key={d.id} className="border-2 border-slate-200 rounded-xl p-5 h-full flex flex-col" data-testid={`document-${i}`}>
                <div className="flex items-start justify-between gap-3">
                  <div className="flex items-start gap-3 min-w-0">
                    <FileText className="w-6 h-6 text-blue-900 flex-shrink-0 mt-1" />
                    <div className="min-w-0">
                      <EText path={`documents.${i}.title`} className="text-xl font-bold text-slate-900 line-clamp-2" />
                      <div className="mt-1"><EArea path={`documents.${i}.description`} className="text-base text-slate-700 line-clamp-2 min-h-[3rem]" rows={2} /></div>
                    </div>
                  </div>
                  <span className={`inline-flex items-center gap-1 text-xs font-bold uppercase tracking-wide border rounded px-2 py-1 flex-shrink-0 ${accessBadge(d.access)}`}>
                    {d.access === "Restricted" && <Lock className="w-3 h-3" />}
                    {d.access}
                  </span>
                </div>

                <div className="mt-3 grid grid-cols-2 gap-4">
                  <div><div className="text-sm font-semibold uppercase tracking-wide text-slate-500 mb-1">Document Date</div><EText path={`documents.${i}.date`} className="text-base text-slate-900" /></div>
                  <div><div className="text-sm font-semibold uppercase tracking-wide text-slate-500 mb-1">Last Updated</div><EText path={`documents.${i}.updated`} className="text-base text-slate-900" /></div>
                  {editMode && (
                    <>
                      <div>
                        <div className="text-sm font-semibold uppercase tracking-wide text-slate-500 mb-1">Category</div>
                        <select data-testid={`doc-category-${i}`} className="editable-input" value={d.category} onChange={(e) => update(`documents.${i}.category`, e.target.value)}>
                          {CATEGORIES.map((c) => <option key={c}>{c}</option>)}
                        </select>
                      </div>
                      <div>
                        <div className="text-sm font-semibold uppercase tracking-wide text-slate-500 mb-1">Access Level</div>
                        <select data-testid={`doc-access-${i}`} className="editable-input" value={d.access} onChange={(e) => update(`documents.${i}.access`, e.target.value)}>
                          {ACCESS.map((a) => <option key={a}>{a}</option>)}
                        </select>
                      </div>
                    </>
                  )}
                </div>

                <div className="mt-auto pt-4 flex items-center gap-3 flex-wrap">
                  {editMode ? (
                    <LinkButton label="View / Download" path={`documents.${i}.link`} variant="secondary" testId={`doc-view-${i}`} />
                  ) : !canOpen(auth?.role, d.access) ? (
                    <span data-testid={`doc-locked-${i}`} className="inline-flex items-center gap-2 text-slate-500 font-semibold border-2 border-slate-200 rounded-lg px-4 py-3 min-h-[56px]">
                      <Lock className="w-4 h-4" /> Requires {d.access} access
                    </span>
                  ) : d.link && !/^#?$/.test(String(d.link).trim()) ? (
                    <LinkButton label="View / Download" path={`documents.${i}.link`} variant="secondary" testId={`doc-view-${i}`} />
                  ) : (
                    <span data-testid={`doc-nofile-${i}`} className="inline-flex items-center gap-2 text-slate-400 font-semibold border-2 border-dashed border-slate-200 rounded-lg px-4 py-3 min-h-[56px]">
                      <FileText className="w-4 h-4" /> No file attached yet
                    </span>
                  )}
                  <DeleteItemButton testId={`delete-doc-${i}`} onClick={() => removeItem("documents", i)} />
                </div>
              </div>
            );
          })}
        </div>

        {visibleCount === 0 && <div className="document-empty" data-testid="documents-empty"><FileText size={28} className="mx-auto mb-3" /><p>No documents found. Try another search or category.</p></div>}
        <div className="mt-6">
          <AddItemButton
            testId="add-document-btn"
            label="Add Document"
            onClick={() => addItem("documents", { id: newId(), title: "Document Link To Be Added", description: "", date: "To be added", updated: "To be added", access: "All Members", link: "#", category: "Reunion" })}
          />
        </div>
      </SectionCard>
    </Layout>
  );
}
