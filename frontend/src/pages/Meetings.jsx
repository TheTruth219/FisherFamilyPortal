import React, { useRef, useState } from "react";
import { Link } from "react-router-dom";
import { CalendarClock, Video, FileText, HelpCircle, ListChecks, Send, Upload, Loader2, Trash2, Paperclip, Clock } from "lucide-react";
import { toast } from "sonner";
import Layout, { SectionCard } from "@/components/Layout";
import { useContent, newId } from "@/context/ContentContext";
import { EText, EArea, AddItemButton, DeleteItemButton, LinkButton } from "@/components/Editable";
import { EDatePicker } from "@/components/DatePicker";
import { api, formatApiErrorDetail } from "@/lib/api";

const TIMEZONES = [
  ["America/New_York", "Eastern (New York)"],
  ["America/Chicago", "Central (Chicago)"],
  ["America/Denver", "Mountain (Denver)"],
  ["America/Phoenix", "Arizona (no DST)"],
  ["America/Los_Angeles", "Pacific (Los Angeles)"],
  ["America/Anchorage", "Alaska (Anchorage)"],
  ["Pacific/Honolulu", "Hawaii (Honolulu)"],
  ["Europe/London", "UK (London)"],
  ["UTC", "UTC"],
];

const timeLabel = (t) => {
  if (!t) return "";
  const [h, m] = t.split(":").map(Number);
  const ap = h < 12 ? "AM" : "PM";
  const hh = h % 12 === 0 ? 12 : h % 12;
  return `${hh}:${String(m).padStart(2, "0")} ${ap}`;
};

function MeetingAttachments({ mi }) {
  const { content, editMode, update } = useContent();
  const meeting = content.meetings.upcoming[mi];
  const attachments = meeting.attachments || [];
  const [uploading, setUploading] = useState(false);
  const inputRef = useRef(null);

  const onFile = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    try {
      const fd = new FormData();
      fd.append("file", file);
      const { data } = await api.post("/files/upload", fd, { headers: { "Content-Type": "multipart/form-data" } });
      const id = newId();
      const today = new Date().toISOString().slice(0, 10);
      update(`meetings.upcoming.${mi}.attachments`, [...attachments, { id, title: data.filename, link: data.url }]);
      update("documents", [
        ...(content.documents || []),
        { id, title: data.filename, description: `Attached to meeting: ${meeting.name || "Meeting"}`, date: today, updated: today, access: "All Members", link: data.url, category: "Meetings" },
      ]);
      toast.success("File attached & added to Documents. Remember to Save.");
    } catch (err) {
      toast.error(formatApiErrorDetail(err.response?.data?.detail) || "Upload failed");
    } finally {
      setUploading(false);
      if (inputRef.current) inputRef.current.value = "";
    }
  };

  const removeAttachment = (id) => {
    update(`meetings.upcoming.${mi}.attachments`, attachments.filter((a) => a.id !== id));
    update("documents", (content.documents || []).filter((d) => d.id !== id));
  };

  if (attachments.length === 0 && !editMode) return null;

  return (
    <div className="mt-4">
      <div className="text-sm font-semibold uppercase tracking-wide text-slate-500 mb-2 flex items-center gap-2"><Paperclip className="w-4 h-4" /> Meeting Documents</div>
      <div className="space-y-2">
        {attachments.map((a) => (
          <div key={a.id} className="flex items-center justify-between gap-3 border border-slate-200 rounded-lg px-3 py-2" data-testid={`meeting-${mi}-attachment-${a.id}`}>
            <a href={a.link} target="_blank" rel="noreferrer" className="inline-flex items-center gap-2 text-blue-900 font-semibold hover:underline min-w-0">
              <FileText className="w-4 h-4 flex-shrink-0" /> <span className="truncate">{a.title}</span>
            </a>
            {editMode && (
              <button type="button" aria-label="Remove attachment" data-testid={`remove-meeting-${mi}-attachment-${a.id}`} onClick={() => removeAttachment(a.id)} className="text-red-700 hover:bg-red-50 rounded p-1">
                <Trash2 className="w-4 h-4" />
              </button>
            )}
          </div>
        ))}
        {attachments.length === 0 && <p className="text-sm text-slate-500">No documents attached yet.</p>}
      </div>
      {editMode && (
        <>
          <input ref={inputRef} type="file" className="hidden" data-testid={`meeting-${mi}-attachment-input`} onChange={onFile} />
          <button type="button" data-testid={`meeting-${mi}-attachment-upload`} onClick={() => inputRef.current?.click()} disabled={uploading}
            className="mt-2 inline-flex items-center gap-2 text-blue-900 font-semibold border-2 border-dashed border-blue-400 rounded-lg px-4 py-2 min-h-[44px] hover:bg-blue-50 transition-colors disabled:opacity-60">
            {uploading ? <Loader2 className="w-5 h-5 animate-spin" /> : <Upload className="w-5 h-5" />}
            {uploading ? "Uploading…" : "Attach document"}
          </button>
        </>
      )}
    </div>
  );
}

function TeamsScheduler({ mi }) {
  const { content, editMode, update } = useContent();
  const u = content.meetings.upcoming[mi];
  const [sending, setSending] = useState(false);

  const sendInvite = async () => {
    if (!u.teamsLink || !/^https?:\/\//i.test(u.teamsLink.trim())) { toast.error("Add a valid Microsoft Teams join link first."); return; }
    if (!u.meetingDate || !u.startTime || !u.endTime) { toast.error("Set the date, start time and end time first."); return; }
    setSending(true);
    try {
      const { data } = await api.post("/meetings/invite", {
        name: u.name || "Family Meeting", meetingDate: u.meetingDate, startTime: u.startTime, endTime: u.endTime,
        timezone: u.timezone || "America/Chicago", teamsLink: u.teamsLink.trim(), purpose: u.purpose || "", agenda: u.agenda || "",
      });
      toast.success(`Calendar invite sent to ${data.sent_to}`);
    } catch (err) {
      toast.error(formatApiErrorDetail(err.response?.data?.detail) || "Could not send invite");
    } finally {
      setSending(false);
    }
  };

  if (!editMode) return null;
  return (
    <div className="mt-4 bg-indigo-50 border border-indigo-200 rounded-lg p-4" data-testid={`teams-scheduler-${mi}`}>
      <div className="text-sm font-semibold uppercase tracking-wide text-indigo-900 mb-3 flex items-center gap-2"><Video className="w-4 h-4" /> Microsoft Teams meeting</div>
      <label className="block text-sm font-semibold text-slate-700 mb-1">Teams join link</label>
      <input data-testid={`meeting-teams-link-${mi}`} className="editable-input" placeholder="https://teams.microsoft.com/l/meetup-join/…"
        value={u.teamsLink || ""} onChange={(e) => update(`meetings.upcoming.${mi}.teamsLink`, e.target.value)} />
      <div className="grid sm:grid-cols-2 gap-4 mt-3">
        <div>
          <label className="block text-sm font-semibold text-slate-700 mb-1">Date</label>
          <EDatePicker path={`meetings.upcoming.${mi}.meetingDate`} testId={`meeting-date-${mi}`} />
        </div>
        <div>
          <label className="block text-sm font-semibold text-slate-700 mb-1">Time zone</label>
          <select data-testid={`meeting-timezone-${mi}`} className="editable-input" value={u.timezone || "America/Chicago"} onChange={(e) => update(`meetings.upcoming.${mi}.timezone`, e.target.value)}>
            {TIMEZONES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>
        </div>
        <div>
          <label className="block text-sm font-semibold text-slate-700 mb-1">Start time</label>
          <input type="time" data-testid={`meeting-start-${mi}`} className="editable-input" value={u.startTime || ""} onChange={(e) => update(`meetings.upcoming.${mi}.startTime`, e.target.value)} />
        </div>
        <div>
          <label className="block text-sm font-semibold text-slate-700 mb-1">End time</label>
          <input type="time" data-testid={`meeting-end-${mi}`} className="editable-input" value={u.endTime || ""} onChange={(e) => update(`meetings.upcoming.${mi}.endTime`, e.target.value)} />
        </div>
      </div>
      <button type="button" data-testid={`send-teams-invite-${mi}`} onClick={sendInvite} disabled={sending}
        className="mt-4 inline-flex items-center justify-center gap-2 min-h-[52px] px-6 font-bold rounded-lg bg-indigo-700 text-white hover:bg-indigo-800 transition-colors disabled:opacity-60">
        {sending ? <Loader2 className="w-5 h-5 animate-spin" /> : <Send className="w-5 h-5" />} {sending ? "Sending…" : "Send Teams Invite to family list"}
      </button>
      <p className="text-sm text-slate-600 mt-2">Emails a calendar invite (.ics) with a Join Teams button to the distribution-list email set in Notifications.</p>
    </div>
  );
}

export default function Meetings() {
  const { content, editMode, addItem, removeItem } = useContent();
  if (!content) return null;
  const m = content.meetings || { upcoming: [], past: [] };

  return (
    <Layout title="Meetings" subtitle="Upcoming and past family meetings, agendas, and minutes." testId="meetings-page">
      <SectionCard title="Upcoming Meetings" testId="upcoming-meetings-section">
        <div className="space-y-4">
          {(m.upcoming || []).map((u, i) => {
            const joinLink = u.teamsLink || (u.location && u.location !== "#" ? u.location : "");
            const timeDisplay = u.startTime ? `${timeLabel(u.startTime)}${u.endTime ? `–${timeLabel(u.endTime)}` : ""}${u.timezone ? ` (${u.timezone.split("/").pop().replace("_", " ")})` : ""}` : (u.time || "—");
            return (
              <div key={u.id} className="border-2 border-slate-200 rounded-xl p-5" data-testid={`upcoming-meeting-${i}`}>
                <div className="flex items-start justify-between gap-3 mb-3">
                  <EText path={`meetings.upcoming.${i}.name`} className="text-xl font-bold text-slate-900" />
                  <DeleteItemButton testId={`delete-upcoming-${i}`} onClick={() => removeItem("meetings.upcoming", i)} />
                </div>
                <div className="grid sm:grid-cols-2 gap-4">
                  <div><div className="text-sm font-semibold uppercase tracking-wide text-slate-500 mb-1">Date</div><EDatePicker path={`meetings.upcoming.${i}.meetingDate`} testId={`meeting-date-view-${i}`} /></div>
                  <div><div className="text-sm font-semibold uppercase tracking-wide text-slate-500 mb-1 flex items-center gap-1"><Clock className="w-3.5 h-3.5" /> Time &amp; Zone</div><span className="text-lg text-slate-900" data-testid={`meeting-time-${i}`}>{timeDisplay}</span></div>
                  <div><div className="text-sm font-semibold uppercase tracking-wide text-slate-500 mb-1">Who Should Attend</div><EText path={`meetings.upcoming.${i}.attendees`} /></div>
                  <div><div className="text-sm font-semibold uppercase tracking-wide text-slate-500 mb-1">RSVP Deadline</div><EText path={`meetings.upcoming.${i}.rsvpDeadline`} /></div>
                </div>

                <TeamsScheduler mi={i} />

                <div className="mt-3">
                  <div className="text-sm font-semibold uppercase tracking-wide text-slate-500 mb-1">Purpose</div>
                  <EText path={`meetings.upcoming.${i}.purpose`} />
                </div>
                <div className="mt-3">
                  <div className="text-sm font-semibold uppercase tracking-wide text-slate-500 mb-1">Agenda</div>
                  <EArea path={`meetings.upcoming.${i}.agenda`} rows={2} />
                </div>

                <MeetingAttachments mi={i} />

                <div className="mt-4 flex flex-col sm:flex-row gap-3 flex-wrap">
                  {joinLink && (
                    <a href={joinLink} target="_blank" rel="noreferrer" data-testid={`join-meeting-${i}`}
                      className="w-full sm:w-auto min-h-[56px] px-6 text-lg font-bold rounded-lg inline-flex items-center justify-center gap-2 bg-indigo-700 text-white hover:bg-indigo-800 transition-colors">
                      <Video className="w-5 h-5" /> Join Microsoft Teams meeting
                    </a>
                  )}
                  <Link to="/contact" data-testid={`upcoming-question-${i}`} className="w-full sm:w-auto min-h-[56px] px-6 text-lg font-bold rounded-lg inline-flex items-center justify-center gap-2 bg-white text-blue-900 border-2 border-blue-900 hover:bg-slate-50 transition-colors">
                    <HelpCircle className="w-5 h-5" /> Submit a Question
                  </Link>
                </div>
              </div>
            );
          })}
        </div>
        <div className="mt-4">
          <AddItemButton
            testId="add-upcoming-btn"
            label="Add Upcoming Meeting"
            onClick={() => addItem("meetings.upcoming", { id: newId(), name: "New Meeting", meetingDate: "", startTime: "", endTime: "", timezone: "America/Chicago", teamsLink: "", attendees: "", purpose: "", agenda: "", attachments: [], rsvpDeadline: "" })}
          />
        </div>
      </SectionCard>

      <SectionCard title="Past Meetings" testId="past-meetings-section">
        <div className="space-y-4">
          {(m.past || []).map((pm, i) => (
            <div key={pm.id} className="border border-slate-200 rounded-xl p-5" data-testid={`past-meeting-${i}`}>
              <div className="flex items-start justify-between gap-3 mb-3">
                <div>
                  <EText path={`meetings.past.${i}.name`} className="text-xl font-bold text-slate-900" />
                  <div className="text-base text-slate-600"><EText path={`meetings.past.${i}.date`} className="text-base text-slate-600" /></div>
                </div>
                <DeleteItemButton testId={`delete-past-${i}`} onClick={() => removeItem("meetings.past", i)} />
              </div>
              <div className="grid sm:grid-cols-2 gap-4">
                <div><div className="text-sm font-semibold uppercase tracking-wide text-slate-500 mb-1">Decisions Made</div><EArea path={`meetings.past.${i}.decisions`} rows={2} /></div>
                <div><div className="text-sm font-semibold uppercase tracking-wide text-slate-500 mb-1">Action Items</div><EArea path={`meetings.past.${i}.actionItems`} rows={2} /></div>
              </div>
              <div className="mt-4 flex flex-col sm:flex-row gap-3 flex-wrap">
                <LinkButton path={`meetings.past.${i}.minutes`} label="View Minutes" icon={ListChecks} variant="secondary" testId={`past-minutes-${i}`} />
                <LinkButton path={`meetings.past.${i}.documents`} label="Supporting Documents" icon={FileText} variant="secondary" testId={`past-docs-${i}`} />
              </div>
            </div>
          ))}
        </div>
        <div className="mt-4">
          <AddItemButton
            testId="add-past-btn"
            label="Add Past Meeting"
            onClick={() => addItem("meetings.past", { id: newId(), date: "To be added", name: "Previous Meeting", minutes: "#", decisions: "", actionItems: "", documents: "#" })}
          />
        </div>
      </SectionCard>

      <div className="flex flex-col sm:flex-row gap-3">
        <Link to="/contact" data-testid="meetings-question-btn" className="w-full sm:w-auto min-h-[56px] px-6 text-lg font-bold rounded-lg inline-flex items-center justify-center gap-2 bg-white text-blue-900 border-2 border-blue-900 hover:bg-slate-50 transition-colors">
          <CalendarClock className="w-5 h-5" /> Submit a Question
        </Link>
      </div>
    </Layout>
  );
}
