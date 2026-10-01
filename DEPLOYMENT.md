# Deploy to Vercel with Upstash Redis

The code is prepared for cloud login and saved addresses. Your Vercel and Upstash accounts still need the configuration below. This change has not deployed the site or created a Redis database.

## 1. Create Redis

In the [Upstash console](https://console.upstash.com/), create a Redis database. Choose a region near your Vercel function region. Copy its **REST URL** and **REST token** (the read/write token, not the read-only token).

Alternatively, connect Upstash through Vercel's Marketplace. Confirm that the resulting variables use the exact names in the next section.

## 2. Set Vercel environment variables

Open your Vercel project → Settings → Environment Variables. Add these for **Production**:

| Name | Value |
| --- | --- |
| `UPSTASH_REDIS_REST_URL` | REST URL from Upstash |
| `UPSTASH_REDIS_REST_TOKEN` | Read/write REST token from Upstash |
| `NEST_STAFF_PASSWORD_RECORD` | Entire contents of `.local/vercel-password-record.txt` |
| `NEST_REDIS_PREFIX` | `nestnnook:production` |
| `NEST_SECURE_COOKIE` | `1` |

The password-record file was exported from your current local password. It contains a salted hash, not the password. It is ignored by Git and excluded from deployments. Paste its contents as one JSON value, without adding quotes around it. Never put these values in Angular source files or commit them.

To export it again, run from the repository root:

```powershell
.\.venv\Scripts\python.exe -m backend.setup_access --export-vercel
```

For Preview deployments, configure the same variable names separately with prefix `nestnnook:preview`. Prefer a separate Redis database and password for previews. Do not reuse the production prefix: prefixes separate sessions, attempt limits, and address lists.

## 3. Update Vercel build settings

This replaces the earlier frontend-only configuration:

| Setting | Value |
| --- | --- |
| Root Directory | Repository root; clear `frontend` |
| Framework Preset | FastAPI |
| Build Command | Use `vercel.json`; remove old `ng build` override |
| Install Command | Default; remove custom frontend-only override |
| Output Directory | Default; remove `dist/...` override |
| Node.js Version | 22.x |

Commit and push the new code and configuration, then redeploy. `vercel.json` installs the Angular dependencies and builds the frontend. `pyproject.toml` selects Python 3.12, declares Python dependencies, and points to `backend.main:app`.

The Python function serves the built frontend after checking staff authentication. Do not copy it to `public/`, add a static frontend deployment, or reintroduce `StaticFiles` mounting without reviewing access control: Vercel can promote static files to its CDN, bypassing the Python login middleware.

## 4. Check the deployed app

- Open the deployment in a private browser window. It should show staff sign-in.
- Before signing in, `/api/addresses` must return 401 and `/main.js` must redirect to sign-in.
- Sign in with your existing staff password.
- Add an address, reload, then confirm the same address appears from a second signed-in device.
- Sign out and confirm the API returns 401 again.
- Download an offer PDF and a Word document.

Missing Redis credentials or password configuration block access. A Redis outage returns 503; it never silently switches to local files or in-memory cloud sessions. A successful local build is not proof of a successful hosted deployment; these checks require the configured live services.

## 5. Import existing property addresses (optional)

New addresses added on Vercel go directly to Redis. Existing `.local/addresses.json` entries are not automatically uploaded. To copy them explicitly:

```powershell
.\.venv\Scripts\python.exe -m backend.migrate_addresses --prefix nestnnook:production
```

Enter the destination REST URL and token when prompted. The token is hidden. The import retains existing cloud addresses and skips duplicates. It does not upload tenant data or remove the local file. Use your preview prefix instead when importing into Preview.

## How storage works

- Random session tokens are sent in Secure, HttpOnly, SameSite=Strict cookies.
- Redis stores only a hash of each token as its key, with an eight-hour expiry.
- Sessions are tied to the configured password hash. Deploying a new password record invalidates old sessions on the new deployment. Disable old deployments if they retain old credentials.
- Logout deletes the session immediately across instances.
- Login attempts are reserved atomically in Redis, limited to five per client IP per 15 minutes. On Vercel, the platform-provided forwarded IP is used; local servers ignore that header.
- Address additions are atomic and case-insensitively deduplicated, with a 500-address limit. Addresses have no expiry.
- Tenant details and generated documents are not saved in Redis. Document processing still receives them transiently on the server.
- Local use without Vercel/Redis variables retains the existing file-backed addresses and in-memory sessions.

## PDF template status

The supplied tenancy, house-rules, and move-in templates are still DOCX files. Vercel cannot run the current Microsoft Word converter. On Linux, the UI defaults to Word downloads for these documents and disables their PDF previews. The offer continues to generate PDF.

Converting the other templates to PDF and mapping their fields is a separate pending task. That must be completed and checked before claiming all-PDF generation works on Vercel.

## Checks run during implementation

The Angular build and local tests cover local login compatibility, Redis operations using a Redis/Lua emulator, shared sessions, logout, expiry, password changes, rate limits, simultaneous address additions, namespace separation, storage failures, and frontend asset authentication. Live Upstash/Vercel integration still requires the account setup above.

References: [Vercel FastAPI](https://vercel.com/docs/frameworks/backend/fastapi), [Upstash REST API](https://upstash.com/docs/redis/features/restapi), [Vercel client IP headers](https://vercel.com/docs/headers/request-headers).
