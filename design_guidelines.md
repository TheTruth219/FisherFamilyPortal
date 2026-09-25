# Fisher Family Portal — Visual Design Guidelines

## 1. Brand Identity & Vision
- **Portal Name**: Fisher Family Portal
- **Brand Core**: Private family space — security, warm trust, continuity, and belonging.
- **Aesthetic Fusion**: Apple-inspired clarity, precision typography, generous layout breathing room, paired with a modernized **Blue & White** color palette.
- **Strict Anti-Patterns**:
  - NO Spotify neon green (`#1ed760`).
  - NO pitch-black Spotify dark theme with green accents.
  - NO third-party or invented logos/names.

---

## 2. Color Palette & Semantic Tokens (Modernized Blue & White)

| Semantic Role | Token Name | Hex Code / Tailwind Equivalent | Description |
| :--- | :--- | :--- | :--- |
| **Canvas** | `--canvas` | `#f5f7fb` | Light blue-white portal backdrop |
| **Surface** | `--surface` | `#ffffff` | White section cards and content containers |
| **Surface Raised** | `--surface-raised` | `#edf2fa` | Soft blue elevated components and hover cards |
| **Stroke / Border** | `--stroke` | `#e1e7f0` | Clean 1px structural dividing lines |
| **Primary Action** | `--brand-blue` | `#285fe7` | Main action buttons, active navigation, focus rings |
| **Primary Navy** | feature panels | `#193e7a` | Deep blue hero cards and feature banners |
| **Sidebar** | navigation | `#142c50` | Family-branded navy navigation |
| **Text Ink** | `--ink` | `#172c4d` | High-contrast navy headings and body text |
| **Text Soft** | `--soft` | `#64748b` | Subtitles and supporting copy |
| **Text Quiet** | `--quiet` | `#6c7d95` | Labels, breadcrumbs, metadata, captions |

---

## 3. Typography & Typesetting
- **Headings Font**: `Work Sans`, sans-serif (Weights: 600, 700)
- **Body Font**: `IBM Plex Sans`, sans-serif (Weights: 400, 500)
- **Scale Hierarchy**:
  - **H1 (Page Title)**: 36px mobile, up to 54px desktop; tight tracking, semibold
  - **H2 (Section Header)**: 16px mobile / 17px desktop; clear, restrained hierarchy
  - **Feature Headline**: 30px mobile, up to 43px desktop
  - **Body**: 13–15px, generous line height; supporting metadata smaller
  - **Labels / Eyebrow**: uppercase with wide tracking and readable blue-gray contrast

---

## 4. Component & Page Layout Guidelines

### 4.1 Layout Shell & Navigation
- Desktop sidebar: 236px fixed, #142c50 navy, pale-blue navigation text, translucent active state. Branding is ONLY the user-selected logo #2 shield/geometric-F symbol; no visible wordmark/subtitle/establishment text. Preserve its portrait proportions, not a stretched square.
- Shared symbol asset: `/brand/fisher-shield.svg`, faithfully extracted from the upper-right logo in the user reference. Navy on light surfaces, white/ice-blue on dark panels. Used by FamilyMark, decorative feature centers, footer, and favicon; screen-reader labels remain.
- Mobile header includes a compact shield home link; desktop/mobile login and mobile navigation use the same text-free symbol. Functional access/privacy icons are not brand marks and keep their semantic meaning.
- Topbar: 78px, translucent white with 20px blur, navy/blue controls; 65px on mobile.
- Main content: white cards on #f5f7fb; generous padding; role-aware mobile Sheet at 390px.

### 4.2 Login Page (`/login`)
- Left story panel: #193e7a deep blue, white and ice-blue typography, decorative interwoven family artwork (not a new logo).
- Right form panel: clean light backdrop, white inputs, blue focus, navy labels.
- Primary sign-in action: #285fe7 blue pill with white label. Mobile retains full Fisher Family brand with a single-column form.

### 4.3 Dashboard (`/dashboard`)
- Featured reunion story: deep blue panel, white/ice-blue copy, blue CTA.
- Collections: blue-tinted artwork tiles and navy labels, 3-column desktop / 2-column mobile.
- Family radar: white announcement cards with understated blue accents.
- Mobile artwork must remain within its container and produce no horizontal overflow.

### 4.4 Content Routes
- All member/admin routes use white section cards, 18px radius, pale blue-gray borders, clear navy headings.
- Document search + category pills combine; count and no-results state are shown.
- Financial tables use tabular numbers; mobile uses labeled stacked records, not off-screen columns.
- Navy balance/overview panels require white/ice-blue text overrides for contrast.
- Dialogs: white surfaces, navy text, blue actions, focus management, Escape/close controls.
- Existing functional handlers, data, access restrictions and integrations remain intact.

---

## 5. Micro-Interactions & Testing Requirements
- **Interactive Feedback**: Transitions restricted to specific properties (`background-color`, `border-color`, `opacity`, `transform`).
- **Focus Indicators**: 2px solid ring in cobalt blue (`#2563eb`) with outline offset.
- **Testing Attributes**: Every interactive and key informational element MUST maintain its specified `data-testid` attribute (e.g. `data-testid="email-input"`, `data-testid="password-login-btn"`, `data-testid="sidebar-nav-dashboard"`).
