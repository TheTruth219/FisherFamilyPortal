import React, { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Search, Mail, Phone, MapPin, Briefcase, Cake, Users, ArrowUpRight, UserCog } from "lucide-react";
import { toast } from "sonner";
import Layout, { SectionCard } from "@/components/Layout";
import { Avatar } from "@/components/Avatar";
import { api, formatApiErrorDetail } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";

const fullName = (m) => [m.first_name, m.last_name].filter(Boolean).join(" ").trim() || m.email;
const fullAddress = (m) => [m.street, [m.city, m.state].filter(Boolean).join(", "), m.zip].filter(Boolean).join(" ").trim();

function ContactRow({ icon: Icon, children, testId }) {
  if (!children) return null;
  return (
    <div className="flex items-start gap-2.5 text-base text-slate-700" data-testid={testId}>
      <Icon className="w-[18px] h-[18px] text-blue-800 mt-0.5 flex-shrink-0" />
      <span className="min-w-0 break-words">{children}</span>
    </div>
  );
}

function MemberCard({ m, isSelf }) {
  const addr = fullAddress(m);
  return (
    <div
      data-testid={`directory-card-${m.email}`}
      className="bg-white border-2 border-slate-200 rounded-2xl p-5 flex flex-col gap-4 hover:border-blue-300 hover:shadow-md transition-all"
    >
      <div className="flex items-center gap-4">
        <Avatar member={m} size="md" testId={`directory-avatar-${m.email}`} />
        <div className="min-w-0">
          <div className="font-heading text-xl font-bold text-slate-900 truncate flex items-center gap-2">
            {fullName(m)}
            {isSelf && <span className="text-xs font-bold uppercase bg-blue-100 text-blue-800 rounded-full px-2 py-0.5">You</span>}
          </div>
          {m.family_branch && <div className="text-sm font-semibold text-blue-800">{m.family_branch}</div>}
          {m.occupation && <div className="text-sm text-slate-500">{m.occupation}</div>}
        </div>
      </div>

      {m.bio && <p className="text-base text-slate-600 leading-relaxed line-clamp-3">{m.bio}</p>}

      <div className="space-y-2 pt-1 border-t border-slate-100">
        <ContactRow icon={Mail} testId={`directory-email-${m.email}`}>
          <a href={`mailto:${m.email}`} className="text-blue-800 hover:underline break-all">{m.email}</a>
        </ContactRow>
        <ContactRow icon={Phone} testId={`directory-phone-${m.email}`}>
          {m.phone ? <a href={`tel:${m.phone}`} className="text-blue-800 hover:underline">{m.phone}</a> : null}
        </ContactRow>
        <ContactRow icon={MapPin} testId={`directory-address-${m.email}`}>{addr || null}</ContactRow>
        <ContactRow icon={Cake} testId={`directory-birthday-${m.email}`}>{m.birthday || null}</ContactRow>
      </div>

      <div className="flex gap-2 mt-auto pt-1">
        <a
          href={`mailto:${m.email}`}
          data-testid={`directory-email-btn-${m.email}`}
          className="flex-1 min-h-[46px] rounded-lg font-bold text-base bg-blue-900 text-white hover:bg-blue-800 transition-colors inline-flex items-center justify-center gap-2"
        >
          <Mail className="w-4 h-4" /> Email
        </a>
        <a
          href={m.phone ? `tel:${m.phone}` : undefined}
          data-testid={`directory-call-btn-${m.email}`}
          aria-disabled={!m.phone}
          className={`flex-1 min-h-[46px] rounded-lg font-bold text-base border-2 inline-flex items-center justify-center gap-2 transition-colors ${
            m.phone ? "border-blue-900 text-blue-900 hover:bg-blue-50" : "border-slate-200 text-slate-400 pointer-events-none"
          }`}
        >
          <Phone className="w-4 h-4" /> Call
        </a>
      </div>
    </div>
  );
}

export default function Directory() {
  const { auth } = useAuth();
  const [members, setMembers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [q, setQ] = useState("");

  useEffect(() => {
    api.get("/directory")
      .then(({ data }) => setMembers(data))
      .catch((err) => toast.error(formatApiErrorDetail(err.response?.data?.detail) || "Could not load the directory"))
      .finally(() => setLoading(false));
  }, []);

  const filtered = useMemo(() => {
    const term = q.trim().toLowerCase();
    if (!term) return members;
    return members.filter((m) =>
      [fullName(m), m.email, m.family_branch, m.city, m.state, m.occupation]
        .filter(Boolean)
        .some((v) => v.toLowerCase().includes(term))
    );
  }, [q, members]);

  const anyBranch = useMemo(() => members.some((m) => (m.family_branch || "").trim()), [members]);

  const groups = useMemo(() => {
    const map = new Map();
    for (const m of filtered) {
      const branch = (m.family_branch || "").trim() || "Other relatives";
      if (!map.has(branch)) map.set(branch, []);
      map.get(branch).push(m);
    }
    return [...map.entries()].sort((a, b) => {
      if (a[0] === "Other relatives") return 1;
      if (b[0] === "Other relatives") return -1;
      return a[0].localeCompare(b[0]);
    });
  }, [filtered]);

  const inputClass = "min-h-[56px] text-lg pl-12 pr-4 border-2 border-slate-300 rounded-xl focus:border-blue-900 focus:ring-2 focus:ring-blue-900 focus:outline-none w-full bg-white text-slate-900";

  return (
    <Layout title="Family Address Book" subtitle="Find and reach any family member." testId="directory-page">
      <SectionCard testId="directory-toolbar">
        <div className="flex flex-col sm:flex-row sm:items-center gap-4">
          <div className="relative flex-1">
            <Search className="w-5 h-5 text-slate-400 absolute left-4 top-1/2 -translate-y-1/2" />
            <input
              data-testid="directory-search"
              className={inputClass}
              placeholder="Search by name, city, branch or email…"
              value={q}
              onChange={(e) => setQ(e.target.value)}
            />
          </div>
          <div className="flex items-center gap-2 text-base font-semibold text-slate-600" data-testid="directory-count">
            <Users className="w-5 h-5 text-blue-800" />
            {filtered.length} {filtered.length === 1 ? "member" : "members"}
          </div>
        </div>
        <Link to="/account" data-testid="directory-edit-profile-link" className="mt-4 inline-flex items-center gap-2 text-base font-semibold text-blue-800 hover:underline">
          <UserCog className="w-[18px] h-[18px]" /> Update your own profile & photo <ArrowUpRight className="w-4 h-4" />
        </Link>
      </SectionCard>

      {loading ? (
        <SectionCard testId="directory-loading"><p className="text-lg text-slate-600">Loading the family address book…</p></SectionCard>
      ) : filtered.length === 0 ? (
        <SectionCard testId="directory-empty">
          <div className="text-center py-8">
            <Users className="w-10 h-10 text-slate-300 mx-auto mb-3" />
            <p className="text-lg text-slate-600">No family members match “{q}”.</p>
          </div>
        </SectionCard>
      ) : (
        anyBranch ? (
          <div className="space-y-8" data-testid="directory-grouped">
            {groups.map(([branch, mems]) => (
              <div key={branch} data-testid={`directory-branch-${branch}`}>
                <div className="flex items-center gap-3 mb-4">
                  <h2 className="font-heading text-2xl font-bold text-slate-900">{branch}</h2>
                  <span className="text-sm font-bold text-blue-800 bg-blue-100 rounded-full px-2.5 py-0.5">{mems.length}</span>
                  <div className="flex-1 h-px bg-slate-200" />
                </div>
                <div className="grid gap-5 sm:grid-cols-2 xl:grid-cols-3">
                  {mems.map((m) => <MemberCard key={m.id} m={m} isSelf={m.id === auth?.id} />)}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="grid gap-5 sm:grid-cols-2 xl:grid-cols-3" data-testid="directory-grid">
            {filtered.map((m) => <MemberCard key={m.id} m={m} isSelf={m.id === auth?.id} />)}
          </div>
        )
      )}
    </Layout>
  );
}
