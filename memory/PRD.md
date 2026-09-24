# Fisher Family Portal — PRD

## Original Problem Statement
Build a simple, mobile-friendly private portal for authorized Fisher family members. One secure starting point for: reunion info, family business, payments, meetings, shared documents, and announcements. MVP — keep structure extremely simple; easy for older members on a phone. No public marketing/history/directory/social features.

## User Choices
- Login: single shared family password
- Admin edit mode: included
- External document/action links: placeholder "#" (wired later)
- Accent: deep navy blue
- App name: "Fisher Family Portal"

## Architecture
- Frontend: React (CRA/craco), react-router, Tailwind, shadcn primitives, lucide icons, sonner toasts. Contexts: AuthContext, ContentContext. Editable.jsx provides in-place admin editing bound to content paths (lodash get/set).
- Backend: FastAPI + MongoDB (motor). JWT in httpOnly cookie `access_token` (7 days). Content stored as a single seeded doc in `settings` (_id=portal_content). Family password hash in `settings` (_id=family_auth). Admin user in `users`. Contact submissions in `contact_messages`.
- Roles: member (shared password) and admin (email+password, unlocks edit mode). Structured so business/committee levels can be added later.

## Personas
- General Family Member — reads reunion/payment/meeting/document info.
- Administrator — edits all portal content inline.

## Implemented (2026-07-29)
- Login page: shared family password + "Administrator sign in" toggle; privacy notice; "Need Access or Login Help?" panel.
- Dashboard: "Important Now" alerts (topic/explanation/deadline/action/button) + 5 nav cards + Contact/Help card.
- Reunion, Family Business, Payments, Meetings, Documents, Contact pages — all sections per spec with editable placeholders.
- Admin edit mode: edit any field, add/remove list items, Save persists via PUT /api/content.
- Contact form stores messages; role-based contacts shown.
- Verified end-to-end (testing agent iteration_1: backend 100%, frontend 100%).
- File & media storage (Emergent object storage): admin-only upload `POST /api/files/upload`, auth-gated view/download `GET /api/files/{id}` (cookie or `?auth=` token). Upload UI appears on every document/action link in admin edit mode (paste link OR upload file). Files tracked in `db.files` with soft-delete flag. (2026-07-29)

## Credentials
See /app/memory/test_credentials.md

## Auth (updated 2026-09-24) — Magic-link, invite-only
- Passwordless **email magic-link** login (Resend managed email). Invite-only: only members added by an admin can sign in; unknown emails get a generic non-enumerating response.
- Members collection: id, email, first_name, last_name, role (member|business_member|committee_member|admin), is_active, token_version, timestamps.
- Admin member management (`/members`): invite (emails sign-in link), change role, deactivate/reactivate (bumps token_version → revokes live sessions), resend link. Admin cannot deactivate or demote self.
- Seeded admin: stephen@cloudpoweredtech.com (self-heals to active admin on startup).
- File downloads now re-check active member + token_version (deactivated users blocked immediately).
- Verified: testing agent iteration_2 (backend 100%, frontend 100%) + manual security checks.

## New-Content Email Notifications (2026-09-24)
- On admin save of content (PUT /api/content), the backend diffs newly-added announcements/meetings/documents by id (against `notified_item_ids` baseline) and, for genuinely new meaningful items, sends ONE email to the family distribution-list address (managed Resend). Never re-notifies edited/existing items; placeholder items are ignored.
- Design: single send to a family group address (admin-configurable on `/members` → "Family Email Notifications") — respects the ~10 sends/10min shared-sender limit and avoids exposing member addresses. Individual 80-way fan-out is intentionally NOT done.
- Verified: settings-only save → 0 emails; new announcement → 1 email (202 Accepted); re-save → 0 (no duplicates).

## Meeting Reminders (2026-09-24)
- Scheduled via `.emergent/crons.yml` (`meeting-reminders`, daily 13:00 America/New_York) → POST `/api/cron/meeting-reminders`.
- Cron endpoint: Bearer `WEBHOOK_CRON_SECRET` (constant-time compare), acks 2xx immediately, backgrounds the work, idempotent on X-Webhook-Id via `cron_runs` (TTL 7d).
- Logic: finds upcoming meetings whose `meetingDate` (new ISO field, admin sets via date picker on Meetings page in edit mode) == tomorrow (America/New_York) and emails ONE reminder to the family distribution list; per-meeting dedupe via `reminders_sent` so it never double-sends. Skips when notifications disabled / no list email.
- Verified in preview: trigger sends 1 email (202) + logs; re-trigger sends 0 (dedupe); 401 on missing/wrong secret; crons.yml validated.
- NOTE: daily cadence is production-safe (>15min rule). Reminder day-boundary uses America/New_York.

## Document Access Control (2026-09-24)
- Server-side role enforcement on file download (`GET /api/files/{id}`): the required level is resolved from the document listing that references the file, so the admin's chosen access label is the single source of truth.
- Role levels: member(1) < business_member(2) < committee_member(3) < admin(4). Access labels: All Members(1), Business Members(2), Committee Members(3), Restricted(4/admin-only). Family Business `restricted:true` docs require committee_member+ (3). Insufficient role → 403.
- UI also gates the View button (shows a lock + "Requires X access" / "Committee only") on Documents and Family Business pages; admins/edit-mode always see it. Backend is the real boundary.
- Verified with real role sessions: Restricted → 200/403/403/403; Business → 200/200/200/403; FB-restricted → 200/200/403/403 (admin/committee/business/member).

## Sample / Demo Data (2026-09-24)
- Admin-only `POST /api/content/load-sample` replaces portal content with clearly-marked fictional SAMPLE data (2027 reunion, schedule, FAQs, business matters, payments, an upcoming + past meeting, documents with all access levels, role-based contacts). Preserves the configured notification list email; resets notified baseline so it does NOT email the family.
- UI: "Demo Data" card on `/members` with a "Load Sample Reunion Data" button (confirm dialog). Everything is labelled "SAMPLE"; admins overwrite with real info via Edit mode anytime.
- Verified: endpoint 200, populates reunion/alerts/meetings/documents, SAMPLE markers present, list email preserved.

## Admin Console & User/Permission Management (2026-09-24)
- `/admin` (admin-only): management cards linking to each editable area + a **Help Requests inbox** reading messages from the Help/Contact form. Endpoints: GET `/api/help-requests` (admin, no _id leaked), PATCH `/api/help-requests/{id}` (status: new|in_progress|resolved, 422 invalid, 404 unknown); `/api/contact` now stamps status 'new'. Filters + "N new" badge in UI.
- User & permission management on `/members` (admin-only): invite by email+role (emails magic-link), change role, deactivate/reactivate (revokes sessions), resend link, plus a **Roles & Permissions** reference explaining what each level unlocks. Duplicate invite -> 409.
- Dashboard shows admin-only cards: Admin Console + Manage Members (hidden for non-admins).
- Help/Contact messages bounded (name<=120, topic<=200, message<=5000, phone<=40) to protect the inbox.
- Verified: testing agent iteration_3 — backend 100% (32 pytest cases incl. help-inbox authz + role-gated file access), frontend 100%, no bugs.

## Edit Member Details (2026-09-24)
- Admins can edit a member's first name, last name, AND email via an "Edit" button on each row (`/members`) opening a modal → PATCH `/api/members/{id}`. Email changes are lowercased and uniqueness-checked (409 on clash); future magic-link sign-ins go to the new email.
- Verified: name+email update → 200; duplicate email → 409; modal renders/saves.

## Backlog (not built)
- P1: Individual access levels (Business/Committee members) gating documents & pages.
- P1: Change family password / manage admins from an admin settings page.
- P2: Admin inbox to view submitted contact messages.
- P2: Migrate FastAPI on_event -> lifespan; add rate limiting & message length caps.
- P2: Wire real SharePoint/Drive links into placeholder buttons.

## Next Tasks
- Await user review; wire real external links; consider access levels if requested.
