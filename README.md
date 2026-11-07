# ARMS 2.0: AI-Powered Airline Reservation and Travel Management System

ARMS 2.0 is a Django application for managing airline reference data, scheduled flights, seat reservations, and travel planning. It includes guest and passenger booking flows, an operations console for administrators, two-factor authentication, live flight tracking through optional third-party providers, and a multilingual travel assistant that can use optional LLM providers.

An ARMS reservation is an internal reservation request. It is not an airline-issued ticket, and the application does not process payments.

Project demonstration: [YouTube video](https://youtu.be/EJkb_slY4gU?si=LH_LaqsJEbSqSGjS)

## Contents

- [Features](#features)
- [Technology](#technology)
- [Project layout](#project-layout)
- [Architecture](#architecture)
- [Domain model](#domain-model)
- [URL map](#url-map)
- [Getting started](#getting-started)
- [Configuration](#configuration)
- [Deployment](#deployment)
- [Management commands](#management-commands)
- [Quality and testing](#quality-and-testing)
- [Engineering conventions](#engineering-conventions)
- [Security and operational notes](#security-and-operational-notes)
- [Upgrade notes for the restructured codebase](#upgrade-notes-for-the-restructured-codebase)

## Features

### Guests

- Search scheduled flights by origin, destination, and date, with time-of-day, price range, and price-sort filters. When filters remove every result, the unfiltered results for that date are shown; when the date has no flights, the next departures on the route are suggested.
- Choose up to six seats on an interactive seat map, enter passenger and contact details, and receive a `GUEST-XXXX-XXXX` booking reference.
- Retrieve or cancel a guest reservation with the booking reference plus the passenger email or last name. Lookups and cancellations are rate limited per client address.

### Passengers

- Register with a username, a separate User ID, contact details, date of birth, and a hashed password-recovery answer.
- Sign in with either the username or the User ID. Sessions last 24 hours.
- Optional email-delivered one-time passcode (two-factor authentication).
- Book seats after confirming the account password and a short arithmetic human check. The verification is valid for three minutes and locks for 15 minutes after five failures.
- Dashboard with recent reservations and unread notifications, a reservation list with self-service cancellation before departure, a profile page, password change, and travel-assistant preferences.
- Password recovery through date of birth and security answer, limited to five attempts within a ten-minute flow.

### Administrators

- Operations console (`/manage/`) for airlines, airports, aircraft, flights, and reservations. Records are archived rather than deleted, so historical flights and reservations stay intact.
- Approve or cancel reservations from the console; approvals and rejections notify the passenger.
- Django admin (`/admin/`) with an upcoming-flights occupancy dashboard, a reservation approval screen, and recurring flight schedules that generate dated flights.

### Travel assistant and tracking

- The assistant answers in English, Spanish, French, German, Japanese, or Hindi. Without a provider key it uses a deterministic local responder backed by a curated destination guide. With a key it calls OpenRouter, Groq, Hugging Face, or OpenAI, and the model may call read-only ARMS tools (flight search, flight details, fare breakdown).
- Booking references typed into chat are never sent to a model; the user is directed to the verified guest lookup instead.
- The flight tracker queries AviationStack when configured, falls back to OpenSky Network, and finally to the ARMS schedule.

## Technology

| Component | Choice |
| --- | --- |
| Language | Python 3.12 or newer (the Docker image uses 3.13) |
| Framework | Django 6.0.10 (latest 6.0 patch release) |
| Database | SQLite for quick local runs, PostgreSQL through `DATABASE_URL` for Docker and production |
| Static files | WhiteNoise 6.12.0 |
| Application server | Gunicorn 26.2.0 |
| HTTP client | requests |
| Images | Pillow (airline logo resizing) |
| Frontend | Django templates, Bootstrap 5, jQuery 3.6, DataTables, Select2 4.1, Font Awesome, Leaflet |

Django 6.1 is available, but WhiteNoise 6.12.0 currently declares support up to Django 6.0, so the project stays on the 6.0 series.

## Project layout

```text
.
├── api/index.py                  Vercel serverless entry point
├── apps/
│   ├── core/                     Cross-cutting infrastructure only (no models)
│   ├── pages/                    Landing page, terms, privacy
│   ├── accounts/                 Custom user model, authentication, 2FA, recovery, profile
│   ├── flights/                  Airlines, airports, aircraft, flights, schedules, search
│   ├── bookings/                 Reservations, seat map, booking flow, guest access
│   ├── notifications/            In-app notifications
│   ├── assistant/                Travel assistant (local responder, LLM client, tools)
│   ├── tracking/                 Live flight lookup providers and schedule progress
│   └── console/                  Administrator operations console
├── config/
│   ├── settings/
│   │   ├── base.py               Settings shared by every environment
│   │   ├── development.py        DEBUG on, console email, local defaults
│   │   ├── production.py         Required secrets, HTTPS hardening, WhiteNoise storage
│   │   └── test.py               Fast hashing, in-memory email and cache
│   ├── environment.py            Typed environment-variable readers
│   ├── admin.py, apps.py         Custom default admin site (Django's documented override)
│   ├── urls.py, wsgi.py, asgi.py
├── static/                       First-party CSS/JS/images and vendored libraries
├── templates/                    Shared layout, navigation, Django admin overrides
├── manage.py
├── Dockerfile, docker-compose.yml, vercel.json
├── requirements.txt              Runtime dependencies (also read by Vercel)
├── requirements-dev.txt          Runtime plus formatting, linting, coverage, pre-commit
├── pyproject.toml, .flake8, .editorconfig, .pre-commit-config.yaml
└── .github/workflows/ci.yml
```

Every app keeps its templates under `templates/<app_label>/` and its tests in a `tests/` package, as recommended by Django for namespaced, reusable apps.

## Architecture

### App responsibilities and dependency direction

Dependencies point in one direction only. Lower layers never import from higher ones.

```mermaid
flowchart TD
    core[core: mixins, middleware, JSON helpers, rate limiter, filters]
    accounts[accounts]
    flights[flights]
    notifications[notifications]
    bookings[bookings]
    assistant[assistant]
    tracking[tracking]
    console[console]
    pages[pages]
    accounts --> core
    flights --> core
    notifications --> core
    bookings --> flights
    bookings --> notifications
    assistant --> bookings
    assistant --> flights
    tracking --> flights
    console --> bookings
    console --> flights
    pages --> flights
    flights -. "views, admin, reports" .-> bookings
```

- `core` holds only infrastructure: the secure-by-default login middleware, page and role mixins, JSON response helpers, the cache-backed rate limiter, the branding context processor, and the `inr` currency filter.
- `flights` owns reference data and flight search. Its domain layer (models, querysets, services) has no knowledge of reservations. Its presentation code (public search views, the admin occupancy screen, and the `list_upcoming_flights` report) imports the bookings availability selector and injects it into the search service, shown as the dotted edge above.
- `bookings` owns reservations and everything about seats. It informs `notifications` about approvals and rejections; notifications never import bookings.
- `console` is a presentation layer for administrators built on the domain services of `flights` and `bookings`.

### Request handling

1. `LoginRequiredMiddleware` (Django 5.1+, subclassed in `apps/core/middleware.py`) makes every view require authentication unless the view class is marked public with `public_view`, which applies Django's `login_not_required`. AJAX requests receive a JSON 401 instead of a login redirect.
2. Role mixins decide who may use a view. `AdministratorRequiredMixin` guards the console; `PassengerAreaMixin` keeps administrators out of passenger and booking pages. A denied browser request is redirected to the user's own dashboard with a message; a denied AJAX request receives JSON 403.
3. Views are class-based and thin. They validate input with Django forms and delegate business rules to services.
4. Services perform the work and raise domain exceptions (for example `ReservationRejected`) that views translate into HTTP responses.

### Where the SOLID principles show up

| Principle | Examples |
| --- | --- |
| Single responsibility | `SeatMap` only computes seat codes, `SeatSelectionStore` only persists a selection in the session, `ReservationVerifier` only handles password and human-check verification, `ReservationSubmission` only parses the posted passenger data, `ReservationService` only creates and cancels reservations, `PasscodeMailer` only delivers one-time codes. |
| Open/closed | New console resources reuse `ModalCreateView`, `ModalUpdateView`, and `ArchiveView` without modifying them. New assistant tools subclass `TravelTool` and are added to the `TravelToolRegistry`. New flight-tracking sources subclass `LiveFlightProvider`. New departure-time filters are new entries in `DEPARTURE_WINDOWS`. |
| Liskov substitution | Every `LiveFlightProvider` returns either a normalized dictionary or `None`, so `LiveFlightLookup` can treat providers interchangeably. Every `TravelTool` exposes the same `definition()` and `run()` contract. |
| Interface segregation | Role checks are small mixins with a single `has_role_access()` hook rather than one large permission class; the guest-access helpers are plain functions instead of a broad service object. |
| Dependency inversion | `FlightSearch` receives a `prepare` callable, so the flights app depends on an abstraction while the view supplies the bookings availability annotation. `TwoFactorChallenge` accepts injectable passcode and mailer collaborators. `LiveFlightLookup` accepts any list of providers. API keys and external configuration come from Django settings, not from `os.environ` inside business code. |

### Data integrity decisions

- Monetary values use `DecimalField`, as recommended for fixed-precision amounts.
- Status and category fields use `TextChoices`.
- Airlines, airports, and aircraft must have unique codes (and airlines and airports unique names) among non-archived records, enforced with conditional `UniqueConstraint`s. Archived codes can be reused.
- A flight must arrive after it departs and must connect two different airports (`CheckConstraint`s).
- A seat can be held by only one pending or approved reservation per flight (conditional `UniqueConstraint`). The booking service also locks the flight row inside a transaction and re-checks availability, and a constraint violation from a concurrent request becomes a 409 response.
- Reference data and flights use `on_delete=PROTECT`, so records with history cannot be deleted by accident; the console archives them instead.
- Seat availability is calculated in a single annotated query (`with_seat_availability`) instead of one query per flight.

### Frontend

- Shared layout CSS and JavaScript live in `static/css/arms.css` and `static/js/arms.js` instead of inline blocks in the base template.
- `arms.js` provides `armsPostForm`, `armsPostAction`, and `armsErrorMessage`, so every AJAX form shows the server's validation message instead of a generic alert. CSRF tokens are read from the form, the `csrf-token` meta tag, or the `csrftoken` cookie, following Django's documented AJAX approach.
- JSON endpoints answer `{"status": "success" | "failed", "msg": ...}` with meaningful HTTP status codes (400, 401, 403, 404, 405, 409, 429). The assistant API uses `message` instead of `msg`.
- The seat map is rendered from the server's own seat list (`json_script`), so the codes a passenger clicks are exactly the codes the server validates.

## Domain model

```mermaid
erDiagram
    USER ||--o| TRAVEL_PREFERENCE : has
    USER ||--o{ RESERVATION : makes
    USER ||--o{ NOTIFICATION : receives
    AIRLINE ||--o{ FLIGHT : operates
    AIRPORT ||--o{ FLIGHT : "origin / destination"
    AIRCRAFT ||--o{ FLIGHT : assigned
    AIRLINE ||--o{ FLIGHT_SCHEDULE : schedules
    AIRPORT ||--o{ FLIGHT_SCHEDULE : route
    AIRCRAFT ||--o{ FLIGHT_SCHEDULE : assigned
    FLIGHT ||--o{ RESERVATION : receives
```

| Model | App | Purpose |
| --- | --- | --- |
| `User` | accounts | Custom user (`AbstractUser`) with User ID (`member_id`), mobile, role (`administrator` or `passenger`), recovery details, and two-factor state. Superusers are created as administrators. |
| `TravelPreference` | accounts | Language, currency, seat class, diet, interests, and budget level used by the assistant. |
| `Airline`, `Airport`, `Aircraft` | flights | Reference data with `is_active` and `is_archived` flags. |
| `Flight` | flights | A dated service. Seat capacity is copied from the aircraft when the flight is saved. |
| `FlightSchedule` | flights | A recurring route definition (daily, weekdays, weekends, weekly, custom days) that generates flights. |
| `Reservation` | bookings | One passenger and seat on a flight, linked to a user or marked as a guest booking, with a unique booking reference. |
| `Notification` | notifications | In-app messages such as reservation decisions. |

Reservation statuses:

| Status | Meaning | Holds the seat |
| --- | --- | --- |
| `pending` | Waiting for administrator approval | Yes |
| `approved` | Confirmed in ARMS | Yes |
| `cancelled` | Cancelled by the passenger, guest, or an administrator | No |
| `rejected` | Rejected by an administrator | No |

A reservation can be cancelled while it is pending or approved and its flight has not departed. Only pending reservations on future flights can be approved.

Seat codes are `B<row><letter>` for business (four seats per row, A to D) and `E<row><letter>` for economy (six seats per row, A to F).

## URL map

| Prefix | Namespace | Purpose |
| --- | --- | --- |
| `/` | `pages` | Landing, `/terms/`, `/privacy/` |
| `/accounts/` | `accounts` | `login/`, `logout/` (POST), `register/`, `two-factor/`, `two-factor/resend/`, `two-factor/toggle/`, `profile/`, `profile/edit/`, `profile/password/`, `profile/preferences/`, `recovery/`, `recovery/verify/`, `recovery/reset/` |
| `/flights/` | `flights` | `search/`, `results/?from_airport=&to_airport=&departure_date=`, `upcoming/` |
| `/bookings/` | `bookings` | `dashboard/`, `mine/`, `<id>/cancel/`, `flights/<id>/seats/`, `flights/<id>/passengers/`, `human-check/`, `verify/`, `submit/`, `confirmation/<reference>/`, `guest/`, `guest/cancel/` |
| `/notifications/` | `notifications` | `<id>/read/` |
| `/assistant/` | `assistant` | Chat page and `api/` |
| `/tracking/` | `tracking` | Tracker page and `api/?flight=` |
| `/manage/` | `console` | Dashboard plus `airlines/`, `airports/`, `aircraft/`, `flights/`, each with `new/`, `<id>/edit/`, `<id>/archive/`; `flights/<id>/`; `reservations/`, `reservations/<id>/`, `reservations/<id>/delete/`, `reservations/<id>/status/` |
| `/admin/` | `admin` | Django admin, `flights/flight/upcoming/`, `bookings/reservation/approval/` |

All state-changing endpoints accept POST only.

## Getting started

### With Docker (recommended for development)

```bash
cp .env.example .env
```

```bash
docker compose up --build web
```

The `web` service runs the development server on <http://localhost:8000> against PostgreSQL, applies migrations on start, and reloads when files change. Then, in another terminal:

```bash
docker compose exec web python manage.py import_data
```

```bash
docker compose exec web python manage.py createsuperuser
```

To run the production image locally (Gunicorn, production settings, plain HTTP) on <http://localhost:8001>:

```bash
docker compose --profile production up --build app
```

### Without Docker

```bash
python3 -m venv .venv
```

```bash
source .venv/bin/activate
```

```bash
python -m pip install -r requirements-dev.txt
```

```bash
python manage.py migrate
```

```bash
python manage.py import_data
```

```bash
python manage.py createsuperuser
```

```bash
python manage.py runserver
```

`manage.py` uses `config.settings.development` by default, which uses SQLite unless `DATABASE_URL` is set. In development, verification emails (two-factor codes) are printed to the console.

## Configuration

Settings are split by environment and selected with `DJANGO_SETTINGS_MODULE`:

| Module | Used by default by |
| --- | --- |
| `config.settings.development` | `manage.py`, the Docker `web` service |
| `config.settings.production` | `config/wsgi.py`, `config/asgi.py`, the Docker image, Vercel |
| `config.settings.test` | Pass it explicitly when running tests |

Environment variables (all optional in development; empty values count as unset):

| Variable | Description |
| --- | --- |
| `SECRET_KEY` | Required in production. Long random value. |
| `SECRET_KEY_FALLBACKS` | Comma-separated previous keys during key rotation. |
| `ALLOWED_HOSTS` | Required in production. Comma-separated host names. |
| `CSRF_TRUSTED_ORIGINS` | Comma-separated origins, for example `https://arms.example.com`. |
| `DATABASE_URL` | Required in production. For example `postgres://user:pass@host:5432/arms`. |
| `DATABASE_CONN_MAX_AGE` | Persistent connection lifetime in seconds. Default `600`; use `0` on serverless platforms without a connection pooler. |
| `SECURE_SSL_REDIRECT` | Production only. Default `True`. |
| `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE` | Production only. Default `True`. |
| `SECURE_HSTS_SECONDS`, `SECURE_HSTS_INCLUDE_SUBDOMAINS`, `SECURE_HSTS_PRELOAD` | Opt-in HSTS. Enable only after HTTPS works end to end. |
| `EMAIL_BACKEND`, `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS` | Production email delivery, needed for two-factor codes. Defaults to SMTP. |
| `DEFAULT_FROM_EMAIL`, `SERVER_EMAIL` | Sender addresses. |
| `DJANGO_ADMINS` | Comma-separated addresses that receive server error emails. |
| `DJANGO_LOG_LEVEL`, `ARMS_LOG_LEVEL` | Log levels for Django and for the `apps` package. Default `INFO`. |
| `SITE_URL` | Public URL sent to OpenRouter as the HTTP referer. |
| `AVIATIONSTACK_API_KEY` | Enables AviationStack live flight lookups. |
| `OPENROUTER_API_KEY`, `GROQ_API_KEY`, `HUGGINGFACE_API_KEY`, `OPENAI_API_KEY` | Server-wide LLM provider keys. The first configured one is used in automatic mode. |
| `AI_API_KEY` | Generic fallback key; the provider is inferred from the key prefix. |

Users can also enter a provider key in the assistant's settings dialog. That key is stored only in their session.

## Deployment

### Vercel (production)

`vercel.json` builds `api/index.py` with the Python runtime and serves the `static/` directory directly. `api/index.py` adds the project root to the import path and exposes the WSGI application from `config/wsgi.py`, which defaults to production settings. Dependencies come from the root `requirements.txt`.

1. Provision a PostgreSQL database and set `DATABASE_URL`, `SECRET_KEY`, `ALLOWED_HOSTS` (for example `your-app.vercel.app`), and `CSRF_TRUSTED_ORIGINS` (for example `https://your-app.vercel.app`) in the Vercel project settings. Consider `DATABASE_CONN_MAX_AGE=0` unless the database provides pooling.
2. Configure SMTP variables if passengers will use two-factor authentication.
3. Apply migrations against the production database from a trusted machine:

   ```bash
   DJANGO_SETTINGS_MODULE=config.settings.production python manage.py migrate
   ```

4. Create an administrator the same way with `createsuperuser`, and optionally load the sample data with `import_data`.

Limitations on Vercel: the serverless filesystem is not persistent, so uploaded airline logos are lost between deployments (use external object storage through the `STORAGES["default"]` setting for durable media). The static route serves the project's `static/` directory only; Django admin assets are not part of it.

### Docker

The `Dockerfile` builds a production image: it installs runtime dependencies, collects static files with WhiteNoise compression, runs as an unprivileged user, and starts Gunicorn on port 8000. Provide the production environment variables and a PostgreSQL database when running it, and run `python manage.py migrate` as a release step.

## Management commands

| Command | Purpose |
| --- | --- |
| `python manage.py import_data` | Loads the sample airlines, airports, aircraft, and flights from `apps/flights/seed_data/`. Flights in the past are moved forward by whole years. Safe to run more than once. |
| `python manage.py generate_recurring_flights --days 30` | Generates flights from active schedules. Use `--schedules CODE ...` to limit it. Without schedules it clones existing flights for each day. `--clear` deletes future flights that have no reservations. |
| `python manage.py list_upcoming_flights --days 7` | Lists upcoming flights with remaining seats. Filters: `--airline`, `--airport`. |
| `python manage.py price_stats` | Prints fare statistics for domestic flights. |
| `python manage.py createsuperuser` | Creates an administrator who can use both the console and Django admin. |

## Quality and testing

```bash
DJANGO_SETTINGS_MODULE=config.settings.test python manage.py test
```

```bash
black --check . && isort --check-only . && flake8 .
```

```bash
pre-commit install
```

The suite contains 146 tests across all apps and runs against SQLite with the test settings or against PostgreSQL with `DATABASE_URL`. The GitHub Actions workflow runs formatting and lint checks, `manage.py check`, a migration drift check, and the full test suite against PostgreSQL.

## Engineering conventions

- Code follows Django's coding style: `black` formatting, `isort` import ordering with the Black profile, `flake8` with an 88-character line limit, absolute imports for other apps and one-dot relative imports within an app.
- First-party code contains no comments or docstrings. Names are chosen to explain intent, and this README is the single place for explanations. Vendored third-party files in `static/vendor/` are unchanged.
- Models follow Django's model style order: fields, managers, `Meta`, `__str__`, `save`, then custom methods.
- Templates follow Django's template style: `{% extends %}` first, a single alphabetized `{% load %}`, and named `{% endblock %}` tags in the shared layouts.
- Modules do not read `django.conf.settings` at import time; settings are read when code runs.
- Log and error messages use `%`-style formatting rather than f-strings, as Django's style guide recommends.

## Security and operational notes

- Never commit secrets. `.env` is ignored by Git and Docker; `.env.example` documents the variables.
- Every view requires authentication unless it is explicitly public, and every state change requires POST with a CSRF token. Logout is POST-only.
- Passwords, security answers, and one-time passcodes are stored as Django password hashes. Passcodes are emailed and are never written to logs.
- Login redirects only follow `next` URLs on the same host.
- Rate limits (guest lookup and cancellation, assistant messages) use Django's cache keyed by `REMOTE_ADDR`. The default local-memory cache is per process; configure a shared cache such as Redis or the database cache before relying on these limits across multiple workers. Behind a proxy, `REMOTE_ADDR` may be the proxy's address.
- Reservation verification throttling is stored in the session, not per account.
- Searching an empty future date on a route automatically creates three placeholder departures for that day, so demo searches always return bookable flights. Remove the `RouteProvisioner` call from `FlightResultsView` if real inventory should be shown only.
- External flight data and LLM answers depend on third-party availability. Terms of Service and Privacy Policy pages are drafts that need operator and legal review.
- Run `python manage.py check --deploy` with production settings before going live.

## Upgrade notes for the restructured codebase

The codebase was restructured from a single `armsApp` application into the apps above. Because app labels and the user model changed, migrations were regenerated from scratch.

- Existing databases are not compatible. Create a new database, run `migrate`, `import_data` (optional), and `createsuperuser`. Data from the previous schema is not migrated.
- URL paths and names changed to the namespaced scheme in the [URL map](#url-map). Old bookmarks no longer resolve.
- Removed files: the stale nested `django_arms/django_arms/` copy of the project, the old single-file `views.py`, `ai_chatbot.py`, `new_views.py`, `views_additions.py`, `models_recurring_flights.py`, `urls_admin.py`, one-off database repair commands (`fix_database`, `fix_all_db_issues`, `rebuild_db`, `create_userprofile_table`, `fix_reservation_table`, `clear_template_cache`), `create_admin` (replaced by `createsuperuser`), unused templates, the unused QR scanner script, unused Bootstrap build variants, the Select2 source tree, an unused CSV directory, Render (`render.yaml`, `DEPLOY_TO_RENDER.md`), the `Procfile`, and the second Dockerfile. Unused Python dependencies (for example NumPy, pandas, OpenCV, django-import-export, django-qr-code, django-simple-captcha, reportlab) were dropped from `requirements.txt`.
- Defects fixed during the restructure:
  - The base template included `TopNavigation.html` while the file was `topNavigation.html`, which broke every page on case-sensitive file systems (Linux, Docker, Vercel).
  - The seat map generated codes such as `1A` with six business and eight economy seats per row, while the server only accepts `B1A` and `E1A` with four and six; every seat chosen in the browser was rejected.
  - Guest booking was documented but the role middleware redirected anonymous visitors from search results, seat selection, and the reservation form to the login page.
  - Pages using Select2 loaded `select2/dist` files that did not exist, causing JavaScript errors; the official Select2 4.1 build is now vendored.
  - Console archive actions sent GET requests to POST-only endpoints and always failed; the airline and airport forms had no code field, so new records could not be created.
  - The upcoming-flights admin screen filtered on a non-existent flight status field and showed an empty arrival column.
  - Passenger "View" buttons pointed at an administrator-only page; they now open the reservation confirmation.
  - Rejected reservations no longer count as occupying a seat, matching the seat map.
  - Reservation approval and rejection in Django admin used GET links; they now use POST forms.
  - The `CA988` sample flight arrived before it departed in ARMS's single time zone; its arrival is now 11 hours 40 minutes after departure.
- Behavior changes: two-factor codes are emailed instead of logged; superusers are administrators; `generate_recurring_flights --clear` no longer deletes flights that have reservations; the dashboard's always-empty "recent searches" table and placeholder "view all notifications" button were removed.
