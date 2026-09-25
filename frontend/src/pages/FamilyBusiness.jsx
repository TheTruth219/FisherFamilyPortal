import React from "react";
import { Link } from "react-router-dom";
import { FileText, HelpCircle, CreditCard, Users, Lock } from "lucide-react";
import Layout, { SectionCard } from "@/components/Layout";
import { useContent, newId } from "@/context/ContentContext";
import { useAuth } from "@/context/AuthContext";
import { EText, EArea, LinkButton, AddItemButton, DeleteItemButton } from "@/components/Editable";

const ROLE_LEVEL = { member: 1, business_member: 2, committee_member: 3, admin: 4 };

export default function FamilyBusiness() {
  const { content, editMode, update, addItem, removeItem } = useContent();
  const { auth } = useAuth();
  if (!content) return null;
  const fb = content.familyBusiness || {};

  return (
    <Layout title="Family Business" subtitle="Current information about family business matters, decisions, payments, and documents." testId="family-business-page">
      <SectionCard testId="fb-intro">
        <EArea path="familyBusiness.intro" rows={3} />
      </SectionCard>

      <SectionCard title="Current Business Matters" testId="fb-matters">
        <div className="space-y-4">
          {(fb.matters || []).map((m, i) => (
            <div key={m.id} className="border-2 border-slate-200 rounded-xl p-5">
              <div className="flex items-start justify-between gap-3 mb-3">
                <EText path={`familyBusiness.matters.${i}.title`} className="text-xl font-bold text-slate-900" />
                <DeleteItemButton testId={`delete-matter-${i}`} onClick={() => removeItem("familyBusiness.matters", i)} />
              </div>
              <div className="mb-3">
                <div className="text-sm font-semibold uppercase tracking-wide text-slate-500 mb-1">Background</div>
                <EArea path={`familyBusiness.matters.${i}.background`} rows={2} />
              </div>
              <div className="grid sm:grid-cols-2 gap-4">
                <div>
                  <div className="text-sm font-semibold uppercase tracking-wide text-slate-500 mb-1">Current Status</div>
                  <EText path={`familyBusiness.matters.${i}.status`} />
                </div>
                <div>
                  <div className="text-sm font-semibold uppercase tracking-wide text-slate-500 mb-1">Decision / Action Required</div>
                  <EText path={`familyBusiness.matters.${i}.action`} />
                </div>
                <div>
                  <div className="text-sm font-semibold uppercase tracking-wide text-slate-500 mb-1">Deadline</div>
                  <EText path={`familyBusiness.matters.${i}.deadline`} />
                </div>
                <div>
                  <div className="text-sm font-semibold uppercase tracking-wide text-slate-500 mb-1">Responsible</div>
                  <EText path={`familyBusiness.matters.${i}.responsible`} />
                </div>
              </div>
              <div className="mt-4">
                <LinkButton label="Related Document" path={`familyBusiness.matters.${i}.documentLink`} variant="secondary" testId={`matter-doc-${i}`} />
              </div>
            </div>
          ))}
        </div>
        <div className="mt-4">
          <AddItemButton
            testId="add-matter-btn"
            label="Add Business Matter"
            onClick={() =>
              addItem("familyBusiness.matters", {
                id: newId(), title: "New Matter", background: "", status: "To be added",
                action: "To be added", deadline: "To be added", responsible: "Family Business Representative", documentLink: "#",
              })
            }
          />
        </div>
      </SectionCard>

      <SectionCard title="Structure and Responsibilities" testId="fb-structure">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="border-b-2 border-slate-200 text-sm uppercase tracking-wide text-slate-500">
                <th className="py-3 pr-4">Matter</th>
                <th className="py-3 pr-4">Responsible Group</th>
                <th className="py-3 pr-4">Primary Role</th>
                <th className="py-3 pr-4">Decision Authority</th>
                <th className="py-3 pr-4">Contact</th>
                {editMode && <th className="py-3"></th>}
              </tr>
            </thead>
            <tbody>
              {(fb.structure || []).map((s, i) => (
                <tr key={s.id} className="border-b border-slate-100 align-top">
                  <td data-label="Matter" className="py-3 pr-4"><EText path={`familyBusiness.structure.${i}.entity`} className="text-base text-slate-900" /></td>
                  <td data-label="Responsible group" className="py-3 pr-4"><EText path={`familyBusiness.structure.${i}.group`} className="text-base text-slate-900" /></td>
                  <td data-label="Primary role" className="py-3 pr-4"><EText path={`familyBusiness.structure.${i}.role`} className="text-base text-slate-900" /></td>
                  <td data-label="Decision authority" className="py-3 pr-4"><EText path={`familyBusiness.structure.${i}.authority`} className="text-base text-slate-900" /></td>
                  <td data-label="Contact" className="py-3 pr-4"><EText path={`familyBusiness.structure.${i}.contact`} className="text-base text-slate-900" /></td>
                  {editMode && (
                    <td className="py-3">
                      <DeleteItemButton testId={`delete-structure-${i}`} onClick={() => removeItem("familyBusiness.structure", i)} label="" />
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="mt-4">
          <AddItemButton
            testId="add-structure-btn"
            label="Add Row"
            onClick={() => addItem("familyBusiness.structure", { id: newId(), entity: "", group: "", role: "", authority: "", contact: "" })}
          />
        </div>
      </SectionCard>

      <SectionCard title="Financial Obligations" testId="fb-obligations">
        <div className="space-y-4">
          {(fb.obligations || []).map((o, i) => (
            <div key={o.id} className="border border-slate-200 rounded-xl p-5">
              <div className="grid sm:grid-cols-2 gap-4">
                <div><div className="text-sm font-semibold uppercase tracking-wide text-slate-500 mb-1">Purpose</div><EText path={`familyBusiness.obligations.${i}.purpose`} /></div>
                <div><div className="text-sm font-semibold uppercase tracking-wide text-slate-500 mb-1">Amount</div><EText path={`familyBusiness.obligations.${i}.amount`} /></div>
                <div><div className="text-sm font-semibold uppercase tracking-wide text-slate-500 mb-1">Who Is Responsible</div><EText path={`familyBusiness.obligations.${i}.responsible`} /></div>
                <div><div className="text-sm font-semibold uppercase tracking-wide text-slate-500 mb-1">Due Date</div><EText path={`familyBusiness.obligations.${i}.dueDate`} /></div>
                <div><div className="text-sm font-semibold uppercase tracking-wide text-slate-500 mb-1">Payment Method</div><EText path={`familyBusiness.obligations.${i}.method`} /></div>
                <div><div className="text-sm font-semibold uppercase tracking-wide text-slate-500 mb-1">Contact</div><EText path={`familyBusiness.obligations.${i}.contact`} /></div>
              </div>
              <div className="mt-3">
                <DeleteItemButton testId={`delete-obligation-${i}`} onClick={() => removeItem("familyBusiness.obligations", i)} />
              </div>
            </div>
          ))}
        </div>
        <div className="mt-4">
          <AddItemButton
            testId="add-obligation-btn"
            label="Add Obligation"
            onClick={() => addItem("familyBusiness.obligations", { id: newId(), purpose: "", amount: "To be added", responsible: "", dueDate: "To be added", method: "", contact: "Family Treasurer" })}
          />
        </div>
      </SectionCard>

      <SectionCard title="Business Documents" testId="fb-documents">
        <div className="space-y-3">
          {(fb.documents || []).map((d, i) => (
            <div key={d.id} className="flex items-center justify-between gap-3 border-b border-slate-100 pb-3">
              <div className="flex items-center gap-3 flex-1 min-w-0">
                <FileText className="w-5 h-5 text-blue-900 flex-shrink-0" />
                <EText path={`familyBusiness.documents.${i}.title`} className="text-lg font-semibold text-slate-900" />
                {d.restricted && (
                  <span className="inline-flex items-center gap-1 text-xs font-bold uppercase tracking-wide bg-red-100 text-red-800 border border-red-300 rounded px-2 py-1">
                    <Lock className="w-3 h-3" /> Restricted
                  </span>
                )}
              </div>
              {editMode && (
                <label className="flex items-center gap-2 text-sm text-slate-600">
                  <input
                    type="checkbox"
                    data-testid={`fb-doc-restricted-${i}`}
                    checked={!!d.restricted}
                    onChange={(e) => update(`familyBusiness.documents.${i}.restricted`, e.target.checked)}
                  />
                  Restricted
                </label>
              )}
              {editMode || !d.restricted || (ROLE_LEVEL[auth?.role] || 1) >= 3 ? (
                <LinkButton label="View" path={`familyBusiness.documents.${i}.link`} variant="secondary" testId={`fb-doc-${i}`} />
              ) : (
                <span data-testid={`fb-doc-locked-${i}`} className="inline-flex items-center gap-2 text-slate-500 font-semibold border-2 border-slate-200 rounded-lg px-3 py-2 min-h-[44px]">
                  <Lock className="w-4 h-4" /> Committee only
                </span>
              )}
              <DeleteItemButton testId={`delete-fb-doc-${i}`} onClick={() => removeItem("familyBusiness.documents", i)} />
            </div>
          ))}
        </div>
        <div className="mt-4">
          <AddItemButton
            testId="add-fb-doc-btn"
            label="Add Document"
            onClick={() => addItem("familyBusiness.documents", { id: newId(), title: "Document Link To Be Added", link: "#", restricted: false })}
          />
        </div>
      </SectionCard>

      <div className="flex flex-col sm:flex-row gap-3 flex-wrap">
        <Link to="/documents" data-testid="fb-view-docs-btn" className="w-full sm:w-auto min-h-[56px] px-6 text-lg font-bold rounded-lg inline-flex items-center justify-center gap-2 bg-blue-900 text-white hover:bg-blue-800 transition-colors">
          <FileText className="w-5 h-5" /> View Business Documents
        </Link>
        <Link to="/contact" data-testid="fb-question-btn" className="w-full sm:w-auto min-h-[56px] px-6 text-lg font-bold rounded-lg inline-flex items-center justify-center gap-2 bg-white text-blue-900 border-2 border-blue-900 hover:bg-slate-50 transition-colors">
          <HelpCircle className="w-5 h-5" /> Submit a Business Question
        </Link>
        <Link to="/payments" data-testid="fb-payment-btn" className="w-full sm:w-auto min-h-[56px] px-6 text-lg font-bold rounded-lg inline-flex items-center justify-center gap-2 bg-white text-blue-900 border-2 border-blue-900 hover:bg-slate-50 transition-colors">
          <CreditCard className="w-5 h-5" /> Make a Business Payment
        </Link>
        <Link to="/meetings" data-testid="fb-meeting-btn" className="w-full sm:w-auto min-h-[56px] px-6 text-lg font-bold rounded-lg inline-flex items-center justify-center gap-2 bg-white text-blue-900 border-2 border-blue-900 hover:bg-slate-50 transition-colors">
          <Users className="w-5 h-5" /> View the Next Business Meeting
        </Link>
      </div>
    </Layout>
  );
}
