import React from "react";
import { useNavigate } from "react-router-dom";
import {
  CalendarHeart,
  Briefcase,
  CreditCard,
  Users,
  FileText,
  LifeBuoy,
  Trash2,
  UserCog,
  LayoutDashboard,
  Banknote,
  FileSpreadsheet,
  ArrowUpRight,
  ArrowRight,
  MapPin,
  Contact,
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
  { key: "disbursements", label: "Disbursements", to: "/disbursements", icon: Banknote, desc: "Family account disbursements & statements" },
];

export default function Dashboard() {
  const navigate = useNavigate();
  const { content, editMode, update, addItem, removeItem } = useContent();
  const { isAdmin, auth } = useAuth();
  const isStaff = !!auth && ["business_member", "committee_member", "admin"].includes(auth.role);

  if (!content) return null;
  const alerts = content.alerts || [];

  return (
    <Layout
      title={`Welcome home${auth?.first_name ? `, ${auth.first_name}` : ""}.`}
      subtitle="A little closer to the people and things that matter."
      showBack={false}
      testId="dashboard-page"
    >
      <section className="home-feature" data-testid="family-feature">
        <div className="home-feature-copy">
          <span className="feature-label"><span /> THE NEXT CHAPTER, TOGETHER</span>
          <h2>More than a reunion.<br />A return to what matters.</h2>
          <p>The familiar faces. The new memories. The feeling of being right where you belong.</p>
          <div className="feature-bottom"><button className="portal-button primary" data-testid="home-reunion-button" onClick={() => navigate("/reunion")}>Explore the reunion<ArrowUpRight size={18} /></button>
            <span className="feature-location" data-testid="home-reunion-location"><MapPin size={15} />{content.reunion?.location || "Details coming soon"}</span>
          </div>
        </div>
        <span className="feature-art-caption">MANY BRANCHES. ONE FAMILY.</span>
      </section>
      <section className="home-announcements" data-testid="important-now-section">
        <div className="home-section-heading">
          <h2>On the family radar</h2><span className="count-pill" data-testid="announcement-count">{alerts.length}</span>
        </div>

        <div className="space-y-4">
          {alerts.length === 0 && <div className="section-card" data-testid="announcements-empty"><p className="text-sm text-slate-500">You’re all caught up. New family updates will appear here.</p></div>}
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

      <section className="home-explore" data-testid="home-explore">
        <div className="home-section-heading"><h2>Your family, at a glance</h2><span>MAKE YOURSELF AT HOME</span></div>
        <div className="collection-grid">
          {NAV.filter((item) => item.key !== "disbursements" || isStaff).map((item, i) => {
            const Icon = item.icon;
            return <button key={item.key} data-testid={`nav-card-${item.key}`} onClick={() => navigate(item.to)} className={`collection-card collection-${item.key}`}>
              <div className="collection-art"><span className="collection-number">0{i + 1}</span><Icon size={46} strokeWidth={1.15} /><span className="collection-orbit" /><span className="collection-arrow"><ArrowUpRight size={18} /></span></div>
              <div className="collection-copy"><h3>{item.label}</h3><p>{item.desc}</p></div>
            </button>;
          })}
        </div>
      </section>
      <div className="home-quicklinks" data-testid="home-quicklinks">
        {[
          { key: "directory", to: "/directory", icon: Contact, title: "Family address book", desc: "Find & reach every family member" },
          { key: "statements", to: "/my-statements", icon: FileSpreadsheet, title: "Your financial picture", desc: "Statements, receipts & peace of mind" },
          { key: "contact", to: "/contact", icon: LifeBuoy, title: "A helping hand", desc: "The right person is one message away" },
          ...(isAdmin ? [
            { key: "admin", to: "/admin", icon: LayoutDashboard, title: "Behind the scenes", desc: "Manage content & family requests" },
            { key: "members", to: "/members", icon: UserCog, title: "Our family circle", desc: "Invite members & manage access" },
          ] : []),
        ].map(({ key, to, icon: Icon, title, desc }) => <button key={key} data-testid={`nav-card-${key}`} onClick={() => navigate(to)} className="home-quicklink"><span className="quicklink-icon"><Icon size={21} /></span><span><strong>{title}</strong><small>{desc}</small></span><ArrowRight size={18} /></button>)}
      </div>
    </Layout>
  );
}
