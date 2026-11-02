# CTF Platform — Project Status

## Overview

A custom Capture The Flag platform built as an **external extension layer**
on top of the upstream [CTFd 3.8.8](https://github.com/CTFd/CTFd) codebase.

All custom code lives in `platform_extension/` outside the CTFd repository,
mounted into the running container via `docker-compose.override.yml`.
The upstream CTFd code is **never modified**.

---

## Repository Layout

```
CTF/
├── CTFd/                                   # Upstream CTFd repo (branch: platform-dev)
│   ├── docker-compose.yml                  # Original — NOT modified
│   ├── docker-compose.override.yml         # ← Our override (auto-loaded by Compose)
│   └── CTFd/                               # CTFd Python package
│       ├── plugins/                        # Stock plugins (challenges, flags, …)
│       └── themes/                         # Stock themes (core, admin, …)
│
└── platform_extension/                     # ← All custom code lives here
    ├── plugins/
    │   └── ctf_platform/
    │       ├── __init__.py                 # Plugin entry point — load(app)
    │       ├── theme_manager.py            # ZIP validation and runtime integration
    │       ├── themes.html                 # Admin theme manager
    │       ├── models.py / roles.py        # Platform roles and access checks
    │       ├── hoster.py                   # Hoster challenge and event-page workflows
    │       ├── hoster_*.html               # Hoster workspace forms
    │       ├── tests/
    │       │   ├── test_theme_manager.py
    │       │   ├── test_roles.py
    │       │   └── test_hoster.py
    │       └── assets/
    │           ├── css/platform.css
    │           └── js/platform.js
    └── themes/
        ├── README.md                       # Theme installation instructions
        └── platform_theme/                 # CTFd theme and assets
```

---

## Milestone Tracker

| Phase | Description | Status |
|-------|-------------|--------|
| 0 | Repository validation & architecture decision | ✅ Complete |
| 1 | Custom plugin skeleton & compose override | ✅ Complete |
| 2 | Plug-and-play theme system | ✅ Complete |
| 3 | Role-based access control (Admin / Hoster / Participant) | ✅ Complete |
| 4 | Challenge & team workflows | ⬜ Not Started |
| 5 | Web challenge deployment (GitHub → Docker) | ⬜ Not Started |
| 6 | Security monitoring | ⬜ Not Started |
| 7 | VM / OVA challenges | ⬜ Not Started |
| 8 | Cloud deployment | ⬜ Not Started |

---

## Phase 0 — Completed

**Findings:**
- CTFd version: **3.8.8** (oss channel)
- Git branch: **platform-dev** (clean, based on upstream commit `8d32061`)
- Docker setup: services `ctfd`, `db` (MariaDB 10.11), `cache` (Redis 4), `nginx`
- Source is bind-mounted read-only (`.:/opt/CTFd:ro`)
- Python code changes require `docker compose restart ctfd` (no auto-reload)
- Plugins are discovered from `CTFd/CTFd/plugins/` via `init_plugins()`
- Themes are discovered from `CTFd/CTFd/themes/` via `get_themes()`

**Architecture Decision:**
External extension directory (`platform_extension/`) mounted via
`docker-compose.override.yml`.  Zero modifications to any CTFd file.

---

## Phase 1 — Completed

**What was created:**
- `platform_extension/plugins/ctf_platform/__init__.py` — Plugin entry point
- `platform_extension/plugins/ctf_platform/assets/css/platform.css` — Placeholder
- `platform_extension/plugins/ctf_platform/assets/js/platform.js` — Placeholder
- `CTFd/docker-compose.override.yml` — Compose volume override

**Verification results:**
- Container restart succeeded and picked up the bind-mounted custom plugin.
- Container startup log verified: `* CTF Platform plugin v0.1.0 loaded successfully`.
- Endpoints verified:
  - `http://localhost:8000/platform/status` → Health check JSON returned.
  - `http://localhost:8000/platform/admin/dashboard` → Accessible with active admin session.
  - CTFd Admin Panel navbar shows the new **Platform** menu link.

**Status:** ✅ Complete. External extension layer architecture successfully validated.

---

## Phase 2 — Completed

**What was created:**
- `platform_extension/themes/platform_theme/` — CTFd-compatible theme with
  custom public templates, styling, and JavaScript.
- Admin-only **Platform Themes** page to install and remove theme ZIPs at
  runtime. Installed themes appear in CTFd's existing theme selector.
- `platform_extension/themes/README.md` — Instructions for ZIP structure and
  theme installation.
- Light and dark color palettes integrated with CTFd's built-in color-mode
  toggle and saved visitor preference.

**Activation:** `platform_theme` is available but does not replace CTFd's
active theme by default. Administrators upload trusted ZIPs from the
**Platform** admin menu, then select one under **Admin Panel → Config → Theme**.
Uploads persist in CTFd's upload volume and take effect without restarting.
The selected theme applies to the whole CTFd instance, matching CTFd's
site-wide theme setting.

**Security:** Uploaded theme templates and JavaScript are executable code.
The upload UI is restricted to CTFd administrators and validates archive
paths, links, duplicate files, and size limits. Only install trusted themes.

**Verification:** Six theme manager tests pass; Compose configuration and
Python syntax checks pass. CTFd startup recognizes the plugin and loads the
theme manager template. Runtime checks verified theme installation,
discovery, template and manifest loading, and static asset serving.

**Status:** ✅ Complete. Both bundled and administrator-uploaded themes are
available to CTFd's theme selector without modifying upstream files.

---

## Phase 3 — Completed

**What was created:**
- A platform-role table and migration for Hoster assignments. Hosters remain
  ordinary CTFd user accounts; they are never promoted to CTFd administrators.
- Admin-only role management at **Platform → Manage Hoster roles**, with grant
  and revoke actions.
- A Hoster workspace at `/platform/hoster/` for creating and editing standard
  challenges, managing static flags and challenge files, and creating/editing
  event pages.
- Separate route guards keep Hosters out of CTFd admin tools and platform role
  management. Revoking the role removes workspace access.

**Verification:** Thirteen plugin unit tests pass. Container-backed workflow
checks passed for admin role assignment/revocation, Hoster challenge and flag
create/edit, challenge file upload/removal, event-page create/edit, and denied
access to admin role management.

**Status:** ✅ Complete. Administrators assign Hosters from the Platform
admin page; Hosters sign in with their existing account and open
`/platform/hoster/`.

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `mysql+pymysql://ctfd:ctfd@db/ctfd` | Database connection string |
| `REDIS_URL` | `redis://cache:6379` | Redis cache URL |
| `SECRET_KEY` | (auto-generated) | Flask secret key |

> **WARNING:** Never commit real secrets to this file.  Use `.env` files
> or Docker secrets for production deployments.

---

## Known Issues

- `docker-compose.override.yml` mounts a single plugin subdirectory into
  the existing read-only volume.  If Docker on Windows has issues with
  overlapping mounts, an alternative is to switch the main volume to
  read-write or use a named volume.
- Gunicorn does not auto-reload; any Python change requires
  `docker compose restart ctfd`.
