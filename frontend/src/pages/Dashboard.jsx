import React from "react";
import { useNavigate } from "react-router-dom";
import {
  CalendarHeart,
  Briefcase,
  CreditCard,
  Users,
  FileText,
  LifeBuoy,
  AlertCircle,
  Trash2,
  UserCog,
} from "lucide-react";
import Layout from "@/components/Layout";
import { useContent, newId } from "@/context/ContentContext";
import { useAuth } from "@/context/AuthContext";
import { EText, EArea, AddItemButton } from "@/components/Editable";

const NAV = [
  { key: "reunion", label: "Reunion", to: "/reunion", icon: CalendarHeart, desc: "Dates, registration, fees, hotel" },
  { key: "family-business", label: "Family Business", to: "/family-business", icon: Briefcase, desc: "Matters, responsibilities, documents" },
  { key: "payments", label: "Payments", to: "/payments", icon: CreditCard, desc: "Reunion and business payments" },
  { key: "meetings", label: "Meetings", to: "/meetings", icon: Users, desc: "Upcoming and past meetings" },
  { key: "documents", label: "Documents", to: "/documents", icon: FileText, desc: "Shared document library" },
];

export default function Dashboard() {
  const navigate = useNavigate();
  const { content, editMode, update, addItem, removeItem } = useContent();
  const { isAdmin } = useAuth();

  if (!content) return null;
  const alerts = content.alerts || [];

  return (
    <Layout
      title="Family Member Dashboard"
      subtitle="Review current announcements, deadlines, payments, meetings, and documents."
      showBack={false}
      testId="dashboard-page"
    >
      {/* Important Now */}
      <section className="mb-10" data-testid="important-now-section">
        <div className="flex items-center gap-2 mb-4">
          <AlertCircle className="w-7 h-7 text-red-700" />
          <h2 className="font-heading text-2xl font-semibold text-slate-900">Important Now</h2>
        </div>

        <div className="space-y-4">
          {alerts.map((alert, i) => (
            <div
              key={alert.id}
              data-testid={`alert-card-${i}`}
              className="bg-red-50 border border-red-200 border-l-8 border-l-red-700 rounded-xl p-5"
            >
              <div className="flex items-start justify-between gap-3">
                <h3 className="font-heading text-xl font-bold text-red-900">
                  <EText path={`alerts.${i}.topic`} className="text-xl font-bold text-red-900" />
                </h3>
                {editMode && (
                  <button
                    data-testid={`delete-alert-${i}`}
                    onClick={() => removeItem("alerts", i)}
                    className="text-red-700 border-2 border-red-300 rounded-lg p-2 hover:bg-red-100"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                )}
              </div>
              <div className="mt-2">
                <EArea path={`alerts.${i}.explanation`} className="text-base text-slate-800" rows={2} />
              </div>
              <div className="mt-3 grid sm:grid-cols-2 gap-3">
                <div>
                  <div className="text-sm font-semibold uppercase tracking-wide text-red-700">Deadline</div>
                  <EText path={`alerts.${i}.deadline`} className="text-base text-slate-900" />
                </div>
                <div>
                  <div className="text-sm font-semibold uppercase tracking-wide text-red-700">Action Required</div>
                  <EText path={`alerts.${i}.action`} className="text-base text-slate-900" />
                </div>
              </div>
              <div className="mt-4">
                {editMode ? (
                  <div className="grid sm:grid-cols-2 gap-2">
                    <EText path={`alerts.${i}.buttonLabel`} />
                    <EText path={`alerts.${i}.buttonLink`} />
                  </div>
                ) : (
                  <a
                    href={alert.buttonLink || "#"}
                    target="_blank"
                    rel="noreferrer"
                    data-testid={`alert-action-${i}`}
                    className="inline-flex items-center justify-center min-h-[52px] px-6 text-lg font-bold rounded-lg bg-blue-900 text-white hover:bg-blue-800 transition-colors"
                  >
                    {alert.buttonLabel || "View"}
                  </a>
                )}
              </div>
            </div>
          ))}
        </div>

        <div className="mt-4">
          <AddItemButton
            testId="add-alert-btn"
            label="Add Alert"
            onClick={() =>
              addItem("alerts", {
                id: newId(),
                topic: "New Alert",
                explanation: "",
                deadline: "To be added",
                action: "",
                buttonLabel: "View",
                buttonLink: "#",
              })
            }
          />
        </div>
      </section>

      {/* Navigation cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
        {NAV.map((item) => {
          const Icon = item.icon;
          return (
            <button
              key={item.key}
              data-testid={`nav-card-${item.key}`}
              onClick={() => navigate(item.to)}
              className="bg-white border-2 border-slate-200 rounded-xl p-8 hover:border-blue-900 hover:shadow-md transition-all flex flex-col items-center text-center gap-4"
            >
              <div className="w-16 h-16 rounded-2xl bg-blue-50 flex items-center justify-center">
                <Icon className="w-9 h-9 text-blue-900" strokeWidth={2} />
              </div>
              <div>
                <div className="font-heading text-xl font-bold text-slate-900">{item.label}</div>
                <div className="text-base text-slate-600 mt-1">{item.desc}</div>
              </div>
            </button>
          );
        })}
      </div>

      {/* Help card */}
      <button
        data-testid="nav-card-contact"
        onClick={() => navigate("/contact")}
        className="mt-6 w-full bg-slate-100 border-2 border-slate-200 rounded-xl p-6 hover:border-blue-900 transition-all flex items-center gap-4 text-left"
      >
        <div className="w-14 h-14 rounded-2xl bg-white flex items-center justify-center flex-shrink-0">
          <LifeBuoy className="w-8 h-8 text-blue-900" />
        </div>
        <div>
          <div className="font-heading text-xl font-bold text-slate-900">Contact or Get Help</div>
          <div className="text-base text-slate-600">Questions about access, payments, meetings, or documents</div>
        </div>
      </button>

      {isAdmin && (
        <button
          data-testid="nav-card-members"
          onClick={() => navigate("/members")}
          className="mt-4 w-full bg-blue-50 border-2 border-blue-200 rounded-xl p-6 hover:border-blue-900 transition-all flex items-center gap-4 text-left"
        >
          <div className="w-14 h-14 rounded-2xl bg-white flex items-center justify-center flex-shrink-0">
            <UserCog className="w-8 h-8 text-blue-900" />
          </div>
          <div>
            <div className="font-heading text-xl font-bold text-slate-900">Manage Members</div>
            <div className="text-base text-slate-600">Invite family members, set roles, and manage access</div>
          </div>
        </button>
      )}
    </Layout>
  );
}
