import React from "react";
import { useNavigate, Link, NavLink, useLocation } from "react-router-dom";
import { ChevronLeft, ChevronRight, LogOut, Pencil, Check, Save, Loader2, Home, CalendarHeart, Briefcase, CreditCard, CalendarDays, FolderOpen, FileSpreadsheet, Banknote, Users, Settings2, LifeBuoy, LockKeyhole, Menu, Contact } from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { useContent } from "@/context/ContentContext";
import { FamilyMark } from "@/components/FamilyArtwork";
import { Sheet, SheetContent, SheetTrigger, SheetTitle, SheetDescription } from "@/components/ui/sheet";

const FAMILY_NAV = [
  { to: "/dashboard", label: "Home", icon: Home },
  { to: "/reunion", label: "Family Reunion", icon: CalendarHeart },
  { to: "/meetings", label: "Meetings", icon: CalendarDays },
  { to: "/documents", label: "Documents", icon: FolderOpen },
  { to: "/directory", label: "Address Book", icon: Contact },
];
const BUSINESS_NAV = [
  { to: "/family-business", label: "Family Business", icon: Briefcase },
  { to: "/payments", label: "Payments", icon: CreditCard },
  { to: "/my-statements", label: "My Statements", icon: FileSpreadsheet },
];

function Navigation({ mobile = false }) {
  const { auth, isAdmin } = useAuth();
  const staff = ["business_member", "committee_member", "admin"].includes(auth?.role);
  const groups = [
    { title: "YOUR FAMILY", items: FAMILY_NAV },
    { title: "FAMILY BUSINESS", items: [...BUSINESS_NAV, ...(staff ? [{ to: "/disbursements", label: "Disbursements", icon: Banknote }] : [])] },
    ...(isAdmin ? [{ title: "ADMINISTRATION", items: [{ to: "/admin", label: "Admin Console", icon: Settings2 }, { to: "/members", label: "Members", icon: Users }] }] : []),
  ];
  return <nav aria-label={mobile ? "Mobile navigation" : "Main navigation"} className="portal-navigation">
    {groups.map((group) => <div className="nav-group" key={group.title}>
      <div className="nav-group-label">{group.title}</div>
      {group.items.map(({ to, label, icon: Icon }) => <NavLink key={to} to={to} data-testid={`${mobile ? "mobile" : "sidebar"}-nav-${to.slice(1)}`} className={({ isActive }) => `sidebar-link ${isActive ? "is-active" : ""}`}>
        <Icon size={19} strokeWidth={1.7} /><span>{label}</span><span className="nav-active-dot" />
      </NavLink>)}
    </div>)}
    <NavLink to="/contact" data-testid={`${mobile ? "mobile" : "sidebar"}-nav-contact`} className="sidebar-link help-nav"><LifeBuoy size={19} strokeWidth={1.7} />Help & contact</NavLink>
  </nav>;
}

export default function Layout({ title, subtitle, showBack = true, children, testId }) {
  const navigate = useNavigate();
  const location = useLocation();
  const { isAdmin, auth, logout } = useAuth();
  const { editMode, setEditMode, dirty, saving, save, reload } = useContent();
  const handleLogout = async () => { await logout(); navigate("/login", { replace: true }); };
  const toggleEdit = async () => {
    if (editMode && dirty) await save();
    if (editMode) await reload();
    setEditMode(!editMode);
  };
  const initials = `${auth?.first_name?.[0] || "F"}${auth?.last_name?.[0] || ""}`;
  const crumb = [...FAMILY_NAV, ...BUSINESS_NAV].find((n) => n.to === location.pathname)?.label || title;

  return <div className="portal-shell" data-testid={testId}>
    <a href="#main-content" className="skip-link" data-testid="skip-to-content">Skip to content</a>
    <aside className="portal-sidebar">
      <Link to="/dashboard" className="portal-brand" data-testid="brand-home" aria-label="Fisher Family Portal home"><FamilyMark testId="brand-home-logo" /></Link>
      <Navigation />
      <div className="sidebar-bottom"><FamilyMark testId="sidebar-footer-logo" /><span>A little closer. Always.</span></div>
    </aside>
    <div className="portal-workspace">
      <header className="portal-topbar">
        <div className="topbar-leading">
          <Sheet key={location.pathname}>
            <SheetTrigger asChild><button className="icon-button mobile-menu-button" aria-label="Open navigation" data-testid="mobile-menu-button"><Menu size={21} /></button></SheetTrigger>
            <SheetContent side="left" className="mobile-nav-sheet">
              <SheetTitle className="portal-brand"><FamilyMark testId="mobile-nav-logo" /><span className="sr-only">Fisher Family Portal navigation</span></SheetTitle>
              <SheetDescription className="sr-only">Navigate your private family portal</SheetDescription>
              <Navigation mobile />
            </SheetContent>
          </Sheet>
          <Link to="/dashboard" className="mobile-brand-link" aria-label="Fisher Family Portal home" data-testid="mobile-brand-home"><FamilyMark testId="mobile-header-logo" /></Link>
          <div className="topbar-breadcrumb"><span>Family portal</span><ChevronRight size={13} /><strong>{crumb}</strong></div>
        </div>
        <div className="topbar-actions">
          <span className="private-pill"><span /> Private family space</span>
          {isAdmin && <button data-testid="edit-mode-toggle" aria-label={editMode ? "Finish editing" : "Edit content"} title="Edit page content" onClick={toggleEdit} className={`topbar-edit ${editMode ? "editing" : ""}`}>
            {saving ? <Loader2 size={15} className="animate-spin" /> : editMode ? <Check size={15} /> : <Pencil size={15} />}<span>{editMode ? "Done" : "Edit page"}</span>
          </button>}
          {isAdmin && editMode && dirty && <button data-testid="save-changes-btn" onClick={save} disabled={saving} className="portal-button primary compact"><Save size={15} />Save</button>}
          <Link to="/account" data-testid="account-link" className="profile-button" aria-label="Your account" title="Your account">{initials}</Link>
          <button data-testid="logout-btn" onClick={handleLogout} className="icon-button" aria-label="Log out" title="Log out"><LogOut size={18} /></button>
        </div>
      </header>
      {isAdmin && editMode && <div className="edit-banner" data-testid="edit-mode-banner"><Pencil size={15} /> You’re editing this page. Save your changes when you’re ready.</div>}
      <main className="portal-main" id="main-content">
        <div className="page-heading">
          <div className="page-eyebrow" data-testid="page-eyebrow">{showBack ? <Link to="/dashboard" data-testid="back-to-dashboard"><ChevronLeft size={14} />BACK TO HOME</Link> : "YOUR PEOPLE. YOUR PLACE."}</div>
          <h1 data-testid="page-title">{title}</h1>
          {subtitle && <p className="page-subtitle" data-testid="page-subtitle">{subtitle}</p>}
        </div>
        <div className={`page-content ${testId || ""}-content`}>{children}</div>
        <footer className="portal-footer"><FamilyMark testId="footer-brand-logo" /><span className="footer-private"><LockKeyhole size={12} /> For family, only.</span></footer>
      </main>
    </div>
  </div>;
}

export function SectionCard({ title, children, testId }) {
  return <section className="section-card" data-testid={testId}>
    {title && <h2 className="section-card-title" data-testid={testId ? `${testId}-title` : undefined}>{title}</h2>}
    {children}
  </section>;
}
