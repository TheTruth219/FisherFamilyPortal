# Fisher Family Portal — PRD

## Original Problem Statement
Build a simple, mobile-friendly private portal for authorized Fisher family members (reunion, family business, payments, meetings, documents, announcements). Later expanded with magic-link + password auth, roles, Admin Console, member management, file storage, email notifications, meeting reminders.

## Latest Feature (2026-06) — Admin Disbursements + Statements + Per-Member Timezone
A capability for Admins to disburse funds from the family business account to members, with per-disbursement receipts, running per-member statements, and (later) real Stripe Connect payouts. Delivered in phases on top of the existing app.

### IMPORTANT build note
The pod started as a bare template; the real app lives at GitHub `TheTruth219/FisherFamilyPortal`. The repo was synced into `/app` and the new features were built on top of the real foundation (single-file `server.py`, cookie-JWT magic-link + password auth, roles `member|business_member|committee_member|admin`, content system, object storage, Resend, cron reminders).

## Architecture
- Frontend: React (CRA/craco, JavaScript .jsx), react-router, Tailwind, shadcn primitives, lucide, sonner. Contexts: AuthContext, ContentContext. Editable.jsx inline admin editing.
- Backend (2026-06 refactor): split from the old single 1826-line `server.py` into modules — `core.py` (Mongo db/client, config constants, object storage, managed email + templates, JWT/auth/security helpers, pydantic models, PDF generation, disbursement/content/reminder helpers, seed data, and the shared `api_router = APIRouter(prefix="/api")`) + per-domain routers (`routes_auth.py`, `routes_members.py`, `routes_content.py`, `routes_contact.py`, `routes_files.py`, `routes_cron.py`, `routes_disbursements.py`, `routes_stripe.py`) + a slim `server.py` (FastAPI app, `include_router`, CORS, startup/shutdown seeding). Routers do `from core import *` and register on the shared `api_router`; behavior is byte-for-byte unchanged (43 routes). Verified regression-free: iteration_13.json 109/109 backend tests. Canonical post-refactor suite: `tests/test_refactor_smoke.py`.
- Money stored as integer `amount_cents`.

## Personas
- Administrator (thetruth219@gmail.com): records/edits disbursements, generates & emails statements, triggers payouts.
- Member: views only their own statements/receipts, acknowledges receipt, sets timezone, completes Stripe onboarding.
- business_member/committee_member: read access scoped by role.

## Implemented — Disbursements feature (2026-06)
- Phase 0 Timezone: `timezone` on member doc, browser auto-detect on first login (AuthContext PATCH /api/auth/timezone confirm=false), editable + confirmable on Account page; public_member exposes timezone/timezone_confirmed.
- Phase 1 Ledger: `db.disbursements` (member_id, member_name/email snapshot, amount_cents, currency, date, category, reason, method[check/zelle/wire/ach/cash/stripe], authorized_by, status[recorded/paid/failed], notes, acknowledged, receipt_path). Immutable `db.audit_log` (create/edit/acknowledge/payout). `db.fund` tracker (total_funded_cents; dispersed/paid computed). Preset categories + custom (upserted to db.disb_categories).
  - Endpoints: GET/POST /api/disbursements, GET /api/disbursements/summary, PATCH /api/disbursements/{id}, POST .../acknowledge, POST .../send-email, GET .../receipt (PDF), GET /api/disbursements/statement/{member_id} (PDF), POST .../statement/{id}/send-email, GET /api/audit/{id}, GET/PUT /api/fund, GET/POST /api/categories, PATCH /api/auth/timezone.
  - Security: admin-only writes; members read only own (server-enforced); business_member+ read all; amounts validated; audit immutable.
  - PDFs: reportlab receipt + statement, stored in object storage, regenerated on demand.
  - Email: Resend-managed; auto-send on create (toggle) + manual resend; emails contain portal link to /my-statements (no raw attachment — proxy limitation).
- Phase 2 Stripe Connect: POST /api/stripe/connect/onboard (Express account + hosted onboarding link), GET /api/stripe/connect/status, POST /api/stripe/payouts/{id} (transfer+payout, updates ledger+audit), GET /api/stripe/tax/{member_id} (1099 threshold flag), POST /api/stripe/webhook (account.updated / payout.* / transfer.reversed, idempotent via db.ledger_events). NOTE: platform test key `sk_test_emergent` may not support real Connect; onboarding fails gracefully (toast, no crash).
- Frontend: /disbursements (admin/staff — stat cards, filters, ledger, create/edit dialog, audit dialog, receipt/statement/email/payout actions), /my-statements (member read-only — summary, acknowledge, receipt/statement download), Account page (timezone + Stripe payout sections). Dashboard cards + AdminHome grid updated; Disbursements nav gated to staff/admin.

## Verification
- testing agent iteration_4: backend 100% (35/35 pytest), frontend 100% of critical flows. Member scoping, RBAC, PDFs, audit, acknowledge, timezone, Stripe graceful — all pass.

## Credentials
See /app/memory/test_credentials.md (admin thetruth219@gmail.com / FisherAdmin#2026; demo victoria@ & james@ / Fisher#2026).

## Update (2026-06, this session) — Repo pulled + Live Payouts scaffold + PDF email attachments
- Pulled the real repo from GitHub `TheTruth219/FisherFamilyPortal` into `/app` (was a blank template). Booted: reportlab installed, env wired (JWT_SECRET, ADMIN_EMAIL/PASSWORD, FRONTEND_URL, EMERGENT_LLM_KEY, EMERGENT_EMAIL_KEY, Stripe keys). Admin + demo members + sample content/disbursements seed on startup.
- PDF Email Attachments: DONE & verified. `_send_email` now supports an `attachments` list; disbursement receipt emails (create + resend) attach `receipt-<id>.pdf`, statement emails attach `statement-<id>.pdf`. The managed email endpoint DOES accept attachments (confirmed HTTP 202 with a real receipt PDF) — the old PRD note that it couldn't was wrong.
- Live Stripe Payouts: real claimable sandbox key wired (replaces `sk_test_emergent`). Connect onboarding/transfer/payout code ready; enabling Connect is a one-time Stripe Dashboard toggle (no API). Onboard now returns an actionable 400 message. Changed business-error HTTP codes 502→400 so Cloudflare passes the JSON through to the UI (CF replaces any 5xx body with its own error page).

## Known limitations / Backlog
- Stripe real payouts require Connect enabled on the platform account. A real claimable Stripe sandbox key is now wired in (test mode); the only remaining step is enabling Connect in the Stripe Dashboard (one-time, not API-doable). Until enabled, onboarding returns a clear 400 message. `sk_test_emergent` (which could not do Connect at all) has been replaced.
- Per-member timezone stored & used for display/Account; meeting reminders still send to the single family distribution list (existing design) rather than per-member fan-out.
- P2 code-health (from review): split server.py into modules; Decimal for money; offload reportlab to executor; audit index/TTL; Stripe idempotency attempt counter; expose method/status enums via config endpoint; max_length on reason/notes.

## Per-Member Timezone Reminder Fan-out + Address Book Branch Grouping + Artwork Removal (2026-06, this session)
- **Meeting reminder fan-out (P1 backlog done):** replaced the single distribution-list reminder with a per-member fan-out. `process_meeting_reminders` now iterates active members, computes "tomorrow" in EACH member's own timezone, and emails them their own reminder at/after a configurable local hour (`notifications.reminderHour`, default 9am). Idempotent per member+meeting+local-date (`db.reminders_sent`). Cron changed to hourly (`.emergent/crons.yml` -> `0 * * * *`). Admin UI (`MembersAdmin.jsx`) now has a `notify-reminder-hour` selector (replaced the old `notify-timezone`). Verified: `backend/tests/test_reminder_fanout.py` PASS; cron endpoint 401/200; iteration_11.json 100%.
- **Address Book grouping (done):** `Directory.jsx` groups members by `family_branch` (heading + count per group, "Other relatives" last). Falls back to a flat grid when no branches are set. Search still filters within groups. iteration_11.json 100%.
- **Decorative artwork removed (user request):** removed the orbital/spirograph `FamilyArtwork` graphic ("OUR STORY CONTINUES" visual) from Login, Dashboard, and Reunion. The shield brand mark (`FamilyMark`) and tagline text are kept. Verified login visually; app compiles clean.

## Deployment readiness (2026-06)
- Ran deployment_agent: found 1 BLOCKER — CORS hardcoded to FRONTEND_URL, ignoring CORS_ORIGINS. Fixed in server.py: CORS now honors CORS_ORIGINS; when "*", uses `allow_origin_regex=".*"` + `allow_credentials=True` so the request Origin is reflected on every response (required for cookie-based JWT auth with withCredentials). Comma-separated list => explicit origins.
- Verified: preflight + actual credential requests from a foreign origin reflect that origin with credentials=true (not "*"). deployment_agent re-run: PASS (no blockers). Browser auth regression: iteration_14.json 100% (login/session/logout, no CORS errors).

## Production admin account (2026-06)
- Added a second admin for prod: stephen@cefisherfamily.org (name "Stephen Fisher", role admin). Seeded idempotently at startup in server.py from new backend/.env keys PROD_ADMIN_EMAIL / PROD_ADMIN_PASSWORD, using the existing bcrypt hash_password. Idempotent: creates if absent; promotes to admin/active and sets password_hash only if missing (won't clobber a later self-set password). Credentials in /app/memory/test_credentials.md.
- Verified: curl login 200 + role=admin + /api/members 200; browser e2e iteration_15.json 100% (admin nav, /members, /disbursements, session persistence, logout) with no regressions. NOTE: prod has its own DB, so this admin materializes when the prod backend boots — (re)deploy to apply.

## MS Teams invites + date pickers + meeting documents (2026-06)
- **Teams meeting invites (manual approach, no MS Graph/IT setup):** admin Meetings editor (edit mode) has a "Microsoft Teams meeting" box — paste Teams join link + pick date + start/end time + timezone, then "Send Teams Invite" emails a proper calendar invite (.ics attachment, METHOD:REQUEST, correct UTC conversion) with a "Join Microsoft Teams meeting" button to the family distribution-list email (Members→Notifications). Backend: POST /api/meetings/invite (require_admin), core.MeetingInvite / build_meeting_ics / send_meeting_invite. Validates https Teams link + that a list email is configured. View mode shows a "Join Microsoft Teams meeting" button when a link is saved.
- **Meeting documents sync:** attaching a file to a meeting (MeetingAttachments) uploads via /files/upload and adds it to BOTH the meeting card AND content.documents (category "Meetings"); removing unlinks from both. Persisted on Save.
- **Calendar date pickers (shadcn Calendar+Popover, YYYY-MM-DD):** new components/DatePicker.jsx exports DatePicker (presentational) + EDatePicker (content-bound). Applied to Meetings (meetingDate), Reunion registration/payment deadlines, and the Disbursement create-form date. Backward-compatible: non-ISO legacy values still display.
- Verified: backend invite curl (bad link→400, valid→200 + .ics sent to delivered@resend.dev); frontend e2e iteration_16.json 100% (7/7 flows incl attachment sync + member read-only regression).
- Backlog notes from QA (non-blocking): add server-side integrity for meeting↔document link (client-side dual-write can leave a dangling ref if the Documents entry is deleted directly); consider orphan-upload cleanup on discard; optional admin delete/archive for disbursement rows.

## Per-member timezone in reminder emails (2026-06)
- Reminder fan-out now converts a meeting's structured schedule (meetingDate + startTime + endTime + source timezone, captured by the Teams scheduler) into EACH member's own timezone. Email shows "Your local time: Wednesday, July 15 · 7:00 PM–8:00 PM EDT" and, when the host zone differs, a "Meeting time (host)" line. Falls back to the old free-form `time` text for meetings without structured times. Helper: core._meeting_time_display; used in send_meeting_reminder.
- Verified: conversion unit-checked across Chicago/NY/LA/Honolulu (6PM CDT → 7PM EDT / 4PM PDT / 1PM HST), unstructured fallback returns None, reminder fan-out test green, ruff F clean.

## Bug fix: past-meeting attachments/minutes indicator (2026-06)
- Report: attaching a document to a Past Meeting showed no attachment/indicator. Cause: past meetings used LinkButton with '#' href fallback, so buttons always rendered regardless of content, and past-meeting docs never synced to the Documents tab (unlike upcoming).
- Fix (Meetings.jsx): generalized MeetingAttachments to scope 'upcoming'|'past' (syncs uploads to Documents tab, category 'Meetings'); new PastMeetingDocs shows a paperclip + count indicator with clickable links in view mode (past-docs-count-<i> / past-doc-<i>-<id>) or a muted 'No minutes or documents posted yet' (past-docs-empty-<i>); edit mode offers a minutes link/upload + synced 'Attach document'. Add-Past-Meeting default now has empty minutes/documents + attachments:[]. Upcoming attachment testids are now scoped (upcoming-meeting-<i>-attachment-...).
- Verified: iteration_17.json frontend 100% (7/7 incl Documents-tab sync, removal from both, minutes link, upcoming regression, member read-only). State cleaned.

## Documents grid uniformity (2026-06)
- Report: document tiles looked staggered (cards sized to content → uneven heights, misaligned buttons). Fix (Documents.jsx): responsive equal-height grid ('grid gap-5 md:grid-cols-2 auto-rows-fr'), each card 'h-full flex flex-col' with the View/Download row pinned via 'mt-auto', title/description clamped (line-clamp-2, description min-h-[3rem]), metadata 2-col. Also: documents with no attached file now show a muted "No file attached yet" instead of a dead View/Download button (mirrors locked-state).
- Verified: iteration_18.json frontend 100% — measured card heights identical (239px, 0px variance) within rows, buttons bottom-aligned, 2-col desktop / 1-col mobile, no overflow, long titles clamped.

## Rename attachments (2026-06)
- Admins can now give an uploaded meeting attachment a friendly display name instead of the raw filename. Meetings.jsx MeetingAttachments: edit-mode rename input (<scope>-meeting-<mi>-attachment-name-<id>) + Open link + remove; renameAttachment syncs the title to both the meeting's attachments[] and the matching content.documents[] entry (by shared id). View mode shows the friendly name. (Documents already had editable titles via EText.)
- Verified: iteration_19.json frontend 100% (upcoming + past rename, Documents-tab sync, Open link intact, remove sync, regression clean; cleanup done).

## Next Tasks
- Await user review. Optionally: real Stripe Connect key for live payouts; full 1099 generation.

## Code-review pass (2026-06)
- Applied the safe, correct fix: replaced 3 silent empty catch blocks with `console.error` logging (AuthContext logout + timezone auto-detect; ContentContext load). iteration_12.json: frontend regression smoke 100%, no regressions.
- Declined (documented): server.py:781 & :1185 "undefined variable" are false positives (except re-raises; generator-scoped `i`). React exhaustive-deps suggestions would introduce infinite loops / reference non-existent locals — mount-once effects are intentional. Component-split / externalize-content / useMemo-micro-perf suggestions are risky churn on tested code with no functional benefit; not done.

## Member Profiles + Family Address Book (2026-06, this session)
- Exact request: "Members need the ability to fill out their profiles and we should surface an 'address book' for the family members to both find other family members and get contact information."
- User choices: fields = phone, mailing address (street/city/state/zip), bio, birthday, family branch/household, occupation, + optional profile photo (initials fallback). Address Book visible to ALL signed-in members (no privacy toggles). Searchable by name; tap-to-email/call per member.
- Backend (server.py): public_member() now exposes phone/street/city/state/zip/bio/birthday/family_branch/occupation/photo_file_id/photo_url. New ProfileUpdate model. Endpoints: PATCH /api/auth/profile (self-edit), POST /api/auth/profile/photo (image upload to object storage, max 5MB, jpg/png/gif/webp), DELETE /api/auth/profile/photo, GET /api/directory (any authed user, active members, alphabetical). Photos served via existing GET /api/files/{id} (default access level 1). No auth/session logic changed.
- Frontend: new Directory.jsx (/directory, searchable grid, mailto/tel actions), shared Avatar.jsx (photo w/ initials fallback), Account.jsx 'Your Profile' section (photo + contact fields), sidebar nav 'Address Book' + dashboard quicklink.
- Verification: iteration_10.json — backend 10/10 pytest, frontend 100% of flows, no bugs. Test file /app/backend/tests/test_profile_directory.py. Test data mutations cleaned afterward.
- Code-health notes (not blocking): photo validated by extension only (trusted family context); birthday is free-form; directory unpaginated (fine at family scale).


## Latest User Direction — Full Visual Redesign (2026-02)
### Exact requirements
- "I want you to visually redesign this entire experience using apple and spotify design aesthetics and first principals"
- Approved a full-experience redesign preserving existing functionality.
- User correction: "This should match the family branding that is in place and not look like Spotify branding."
- Final palette direction: "modernize the portal's color pallet but keep it in the blue and white range"

### Implemented
- Final design is LIGHT BLUE AND WHITE, not the initial dark/green proposal. Preserve Fisher Family branding and the original lock/security motif; no Spotify-green branding or invented F wordmark.
- Shared palette: canvas #f5f7fb, white cards, navy #142c50 sidebar, #193e7a feature panels, #285fe7 actions, navy #172c4d text, ice-blue decorative artwork.
- Rebuilt shared shell with persistent role-aware sidebar, active navigation, glass-white topbar, profile shortcut, editing controls, accessible mobile Sheet, and footer.
- Redesigned password/magic-link login visuals and verification state without changing backend authentication/session logic.
- Rebuilt dashboard with personalized greeting, reunion feature, family collections, announcements and quick links. Existing actual content/data preserved.
- Applied responsive design to reunion, business, meetings, payments, documents, contact, account, disbursements, own statements, admin console, and members.
- Added document title/description search combined with category filters, result count, and no-results state.
- Added account profile presentation; transformed financial tables into labeled stacked records on mobile; preserved all receipt/statement, ledger, audit, and payout actions.
- Replaced member edit/disbursement/audit overlays with accessible shadcn Dialogs (focus management, Escape and close controls).
- Fixed QA issues: mobile SVG overflow, member direct-access routes mounting unauthorized pages, and invalid dynamic option children. Added allowedRoles to ProtectedRoute; /members and /admin require admin; /disbursements allows business_member, committee_member, admin. Backend authorization unchanged; consulted integration playbook.
- No backend/API/payment/email/storage implementation changes or credential changes. No new mocked integrations.

### Verification
- Production frontend build compiled successfully.
- /app/test_reports/iteration_8.json: all routes checked at 1920x800 and 390x844; zero horizontal-overflow offenders, no reported UI/console bugs.
- Verified admin/member login/navigation, member role redirects before protected API calls, document search/filter/no-results, mobile navigation, dialog Escape/close, member edit/save, timezone save/persistence/restore, ledger creation with send_email=false, edit/persistence, audit, receipt PDF, member statement scoping. Test ledger/audit records removed; timezone restored; no test emails sent.
- Inline content edit controls/rendering verified; content save handler remained unchanged and was not re-exercised in the final regression.
- Prior backend suite (iteration_6): 38/38 passing. Backend not modified in this redesign.
- Await user aesthetic review of final blue-white direction.

### Reference files
- Design system: frontend/src/App.css, index.css; /app/design_guidelines.md is the implementation source of truth.
- Shared shell/artwork: components/Layout.jsx, FamilyArtwork.jsx; dialogs/sheet under components/ui.
- Screens/pages: frontend/src/pages/*.jsx. Route roles: App.js and components/ProtectedRoute.jsx.

### Remaining Scope / Prioritized Backlog (not part of visual redesign)
- P1: Per-member timezone meeting reminder fan-out.
- P2: Year-end admin 1099 threshold center/full generation.
- Existing integration limitation: Stripe remains TEST MODE; Connect activation is still required for payouts. Demo email addresses may be undeliverable. No live-payout claim is made.
- Optional code-health backlog: modularize server.py, Decimal money handling, async PDF work, audit indexes, payout idempotency improvements, explicit field bounds/enums. No unrelated backend refactoring performed.

## Latest Branding Update — Logo #2, Symbol Only (2026-02)
- Exact request: "Use logo #2 to replace the lock and logo's in the portal. If you have a better design than that logo present it". Final clarification: "no, only use the logo without the text".
- Selected the upper-right shield/geometric-F from the user’s four-logo reference. Extracted and vector-traced ONLY that symbol; excluded option number, family-name wordmark, subtitle, establishment line, paper, and wood background. No alternate logo substituted.
- Source: /app/design-assets/fisher-logo-options.png (user attachment); extraction script /app/design-assets/extract_logo.py; final static assets /app/frontend/public/brand/fisher-shield.svg and fisher-shield.png. SVG preserves the source portrait proportions (107.06 × 145.96 viewBox).
- Shared FamilyMark renders the symbol via CSS mask with navy/blue or white/ice-blue coloring. Applied on desktop/mobile login, desktop sidebar, mobile header home link, mobile navigation, sidebar small mark, page footer, decorative art centers, and browser favicon.
- Removed visible branding wordmark/subtitle text. Accessible names and screen-reader navigation title retained. Ordinary page copy and functional privacy/access icons remain unchanged.
- Browser title now Fisher Family Portal. Existing blue-and-white palette preserved. No backend/API/auth/credential/data changes or new integrations.
- Verification: production build successful; /app/test_reports/iteration_9.json PASS. Checked logo fidelity, symbol-only display, SVG serving/favicon, branding navigation, mobile drawer, accessibility labels and zero overflow at 1920x800 and 390x844. No new issues, test data or emails.
- Backlog unchanged: per-member timezone reminder fan-out, year-end 1099 center. Optional enhancement: carry the chosen shield into generated PDF receipts/statements.

## Meeting Template Sections (2026-06)
- Request: "When editing meetings, there should be the ability to choose from a template of things to surface in the saved product... a description section... a link for somebody to view the recording." User choices: available on BOTH upcoming & past meetings; template menu = Description (text), Recording (link → 'View recording' button, opens new tab), Decisions Made (text); only filled sections shown in view mode; each added section removable.
- Implementation: new `MeetingSections` component in frontend/src/pages/Meetings.jsx. Stores `meeting.sections = [{id, type, value}]` (type ∈ description|recording|decisions) on each upcoming/past meeting. Edit mode shows an "Add section from template" picker (data-testids add-section-<scope>-<mi>-<type>) + per-section remove (remove-section-<scope>-<mi>-<id>). View mode renders only non-empty sections. addItem seeds include sections:[]. No backend change (content is a loose dict; sections persist via PUT/GET /api/content). Existing fixed Decisions Made / Action Items on past meetings retained.
- Verification: /app/test_reports/iteration_22.json PASS (100% frontend). Add/fill/remove/save/persist across reload all work; regressions (Teams scheduler, Purpose/Agenda, attach-document→Documents) clean. Test data cleaned up (sections=[]).

## Session ops notes (2026-06)
- Synced workspace to GitHub main (repo TheTruth219/FisherFamilyPortal) via manual file copy (platform GitHub is push-only; no pull-into-job). Added reportlab==5.0.1.
- STRIPE_API_KEY added to backend/.env (Emergent shared TEST key sk_test) so deploy snapshot captures it; production needs a redeploy (and a real LIVE key for real payouts). STRIPE_WEBHOOK_SECRET not set.
- Preview admin password reset to FisherAdmin2026! (stephen@cloudpoweredtech.com); see memory/test_credentials.md. Production admin seeds from ADMIN_EMAIL + ADMIN_PASSWORD secrets (both SET in prod).

