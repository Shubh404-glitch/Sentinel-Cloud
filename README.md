# Sentinel Cloud

Sentinel Cloud is the web-based cloud edition of SentinelScan, providing centralized security scanning, asset visibility, project management, reporting, user management, and security-focused application controls.

## Version

**Sentinel Cloud V1.0**

V1.0 frontend and backend development and QA are complete.

---

## Overview

Sentinel Cloud provides a web interface for managing security scanning data and related security operations.

The application consists of:

* **Frontend** — Next.js web application
* **Backend** — FastAPI API
* **Authentication** — JWT-based authentication
* **Database** — Backend-managed application database

The frontend communicates with the backend through authenticated API requests.

---

## V1.0 Features

### Dashboard

Provides the main Sentinel Cloud overview and security information.

### Assets

Provides visibility into managed/scanned assets.

### Projects

Provides project organization and project-related security data.

### Reports

Provides access to security scan reports and report information.

### Users

Provides user-management functionality.

### Settings

Provides application settings and configuration information.

### Authentication

V1.0 includes JWT-based authentication.

The authentication flow includes:

* Login
* Access-token handling
* Authenticated API requests
* Protected routes/endpoints
* Current-user authentication
* Logout

Authentication was manually tested and verified during V1.0 QA.

### Preferences Bubble

Sentinel Cloud V1.0 includes a floating user-preferences bubble.

The bubble provides:

#### Theme

* Dark
* Light
* System

The selected theme changes **only the Bubble/Preferences interface** and does not change the main Sentinel Cloud GUI.

#### Position

* Bottom Left
* Bottom Right
* Top Left
* Top Right

The Preferences menu automatically opens in a viewport-safe direction based on the bubble position.

#### Size

* Small
* Medium
* Large

Size changes both:

* The floating bubble
* The Bubble Preferences interface

It does not resize the main Sentinel Cloud interface.

Bubble preferences are stored locally in the browser.

No backend endpoint is required for these V1.0 preferences.

---

# Technology Stack

## Frontend

* Next.js
* React
* TypeScript
* Tailwind CSS
* Next.js App Router

The frontend source is organized under:

```text
frontend/
└── src/
    ├── app/
    ├── components/
    ├── lib/
    └── ...
```

Important layout components include:

```text
src/components/layout/
├── DashboardLayout.tsx
├── Navbar.tsx
├── Sidebar.tsx
└── Bubble.tsx
```

## Backend

* Python
* FastAPI
* JWT authentication
* Alembic/database migrations
* Python virtual environment

The backend contains the API, authentication, database models, report ingestion, and related application services.

---

# Authentication

Sentinel Cloud uses JWT-based authentication.

Authenticated requests use the Bearer token mechanism:

```text
Authorization: Bearer <access_token>
```

Authentication was tested through the backend API and frontend application.

Verified areas include:

* Login
* JWT token generation
* Authenticated requests
* `/auth/me`
* Protected endpoints
* Frontend/backend authentication communication
* Logout

---

# Report Ingestion

The backend provides report ingestion functionality.

The V1.0 ingestion flow was tested using:

* Project identification
* API key authentication
* Report submission
* Report validation
* Report processing

A successful report ingestion request returned:

```text
201 Created
```

---

# Running Locally

## Frontend

Navigate to the frontend directory:

```powershell
cd frontend
```

Install dependencies if required:

```powershell
npm install
```

Start the development server:

```powershell
npm run dev
```

The Next.js development server can then be accessed through the local development URL displayed by Next.js.

---

## Backend

Navigate to the backend directory:

```powershell
cd backend
```

Activate the Python virtual environment:

```powershell
.venv\Scripts\Activate.ps1
```

Start the FastAPI application using Uvicorn.

The exact Uvicorn application/module path depends on the backend project configuration.

The FastAPI Swagger documentation is available at:

```text
/docs
```

when the backend server is running.

---

# Environment Variables

Environment files are intentionally excluded from source control.

The project protects environment files through `.gitignore` rules.

Examples include:

```text
.env
.env.local
.env.production
```

Actual secrets must never be committed to the repository.

Environment variables should be configured through the appropriate local development environment or deployment platform.

---

# Project Structure

The high-level project structure is:

```text
sentinelscan-cloud/
│
├── backend/
│   ├── .gitignore
│   ├── src/
│   ├── .venv/
│   └── ...
│
└── frontend/
    ├── src/
    │   ├── app/
    │   │   ├── assets/
    │   │   ├── dashboard/
    │   │   ├── login/
    │   │   ├── projects/
    │   │   ├── reports/
    │   │   ├── settings/
    │   │   └── users/
    │   │
    │   ├── components/
    │   │   ├── layout/
    │   │   │   ├── DashboardLayout.tsx
    │   │   │   ├── Navbar.tsx
    │   │   │   ├── Sidebar.tsx
    │   │   │   └── Bubble.tsx
    │   │   ├── ...
    │   │
    │   ├── lib/
    │   └── ...
    │
    ├── package.json
    ├── package-lock.json
    └── ...
```

---

# V1.0 QA Status

Sentinel Cloud V1.0 frontend and backend QA has been completed.

## Frontend

* Next.js setup — Complete
* UI/Tailwind foundation — Complete
* Layout — Complete
* Navigation — Complete
* Dashboard — Tested
* Assets — Tested
* Projects — Tested
* Reports — Tested
* Users — Tested
* Settings — Tested
* Authentication — Tested
* Backend communication — Tested
* Preferences Bubble — Tested
* Theme — Tested
* Position — Tested
* Size — Tested
* Browser console/error checks — Completed

**Frontend V1.0 QA: 100% complete**

## Backend

* FastAPI setup — Tested
* Database/models — Tested
* Admin setup — Tested
* Alembic/database configuration — Tested
* Authentication — Tested
* JWT authentication — Tested and verified
* Protected endpoints — Tested
* `/auth/login` — Tested
* `/auth/me` — Tested
* Dashboard endpoint — Tested
* Report ingestion — Tested
* Project/API-key ingestion flow — Tested
* Report processing — Tested
* Swagger documentation — Tested
* Frontend/backend communication — Tested
* Complete backend endpoint QA — Complete

**Backend V1.0 QA: 100% complete**

---

# Security Notes

Do not commit:

* Passwords
* JWT secrets
* API keys
* Database credentials
* Private keys
* Production environment variables
* Access tokens

Environment files are excluded from source control through `.gitignore`.

The backend should keep sensitive configuration server-side.

---

# V1.0 Scope

V1.0 is considered the completed initial Sentinel Cloud release.

The focus of V1.0 is a stable web application with:

* Authentication
* Dashboard
* Assets
* Projects
* Reports
* Users
* Settings
* Backend API communication
* Report ingestion
* Preferences Bubble
* Completed frontend QA
* Completed backend QA

---

# V2.0 Roadmap

The following items are intentionally deferred to Sentinel Cloud V2.0.

### Dynamic Security Status

The current Security status implementation can remain informational/static in V1.0.

V2.0 can introduce backend-sourced security status data and the required API integration.

### Backend-Sourced General Settings

General Settings integration with backend data is deferred to V2.0.

### Raw Report Data

The Reports section can be enhanced in V2.0 so that:

```text
Raw Data: Available
```

becomes expandable/clickable and allows authorized users to view the actual raw report JSON/data directly in the frontend.

### Additional Backend Endpoints

Any new backend endpoints required by V2.0 functionality will be designed and implemented as part of V2.0 rather than added unnecessarily to V1.0.

---

# Release Status

**Sentinel Cloud V1.0**

Frontend:

**100% QA complete**

Backend:

**100% QA complete**

V1.0 is ready for final Git checkpoint and release tagging.

---

## License

Add the project's applicable license here before public distribution.
