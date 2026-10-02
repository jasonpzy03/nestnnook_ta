# Nest & Nook tenancy documents

Mobile-friendly Angular TypeScript app with a Python FastAPI backend. Local file storage, with Redis for cloud login and saved addresses. Documents in `agreements/` provide the base templates. Requested field and fee changes are applied during generation.

## Run

Requirements: Node.js 22.12+ and Python 3.12+. Microsoft Word is needed only when rebuilding PDF templates after source changes.

```powershell
.\start.ps1
```

Open http://localhost:8000. On a phone using the same Wi-Fi, open `http://<computer IPv4 address>:8000`. Keep the computer and app running. Use `ipconfig` to find the address.

## Generate documents

1. Choose the documents needed. Each card has a Create button. House rules asks for optional tenant details, then review; other selections show only their required steps.
2. Choose AC or non-AC, enter unit and room numbers, select a saved property address, and enter dates and payments. Add address saves an option for all staff devices. The 6 months / 1 year buttons calculate expiry from move-in; changing move-in recalculates the selected term.
3. Complete inventory and condition fields only when the move-in form is selected.
4. Preview and download the selected documents.

**PDF** fills converted copies of the Word templates. All document types work without Word at runtime. **Word** downloads filled `.docx` templates, including the offer. Multiple documents arrive in one ZIP. See [template editing instructions](agreements/README.md) for editing the offer and refreshing its PDF copy.

On iPhone, choose **Share PDFs**, wait for preparation, then tap **Share PDFs** in the dialog and choose WhatsApp and the customer. Each document remains a separate PDF. The second tap opens the native share sheet directly, as required by mobile browsers. The app checks support for the actual files and offers individual Share/Download buttons as a fallback. Use the HTTPS deployment in Safari. WhatsApp availability and acceptance of multiple files depend on the installed app. Files stay in browser memory until the dialog closes; nothing is automatically sent or stored on the server. The Download action still provides the existing ZIP for multiple documents.

Offer invoice numbers are generated automatically when blank, for example `NN-20261002-A1B2C3D4E5`. The date uses the signing date and the suffix is random, not sequential. The same number is retained for previews, downloads and sharing within the current form, and included in saved drafts. Start a new tenancy for a new offer; manually entered invoice numbers are preserved.

Company details are editable. Drafts are saved only when you choose Save draft. Reloading the page clears unsaved entries. PDF generation runs in memory; the app keeps no tenant records. Saved drafts and downloads contain the entered personal information.

## Original template mapping

- **Tenancy:** uses the selected AC or non-AC DOCX, preserving its separate clauses, tables, styles, signature sections and payment rows. Existing non-AC air-conditioning references remain as supplied. Company bank and signature details replace the personal landlord details in the non-AC template.
- **House rules:** replaces tenant name and ID. Rules and original operational contacts remain unchanged.
- **Move-in:** fills original registration tables and both copies of embedded inventory and bank text boxes. Sample inventory, damage notes and card numbers are cleared. Inventory defaults to quantity 1 and Good. The revised `1. Move in Form - quantity.docx` adds a separate Qty column in both text box copies; it is the active template because the original file was locked when editing. Unused fields and zero amounts print as a dash. Drawer selection updates the original checkbox mark.
- **Offer:** fills `4. Letter of Offer to Rent.docx` using editable placeholders. Its converted PDF follows the same source. The offer wording, Nest & Nook branding, payment rows and blank signature spaces are retained; room transfer fees remain excluded from the offer only.
- **Enclosure:** the optional acknowledgement is included by default in both formats. Its wording is retained from the original third page. Staff can exclude it where its statements do not apply.
- **Payments:** each document retains its original rows. The non-AC tenancy has no access deposit or agreement fee row. Offer total = refundable room deposit + refundable access card deposit + advance rental + agreement fee. Rent and parking are not added again.

PDF fields have fixed space. Entries that cannot fit produce an error identifying the field; shorten the entry or download Word format. Word text wraps within original cells, so preview long names, addresses and remarks before signing.

## Development and checks

```powershell
.\.venv\Scripts\python.exe -m pip install -r backend/requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest backend/tests -q -p no:cacheprovider
cd frontend
npm run build
```

Run `npm start` in `frontend` for Angular development on port 4200 (API proxy to 8000). Python serves the production build on port 8000.

Tests check unchanged DOCX package parts and formatting properties, fixed clauses, sample-data removal, PDF page geometry and drawing preservation, exact decimal totals, validation and overflow errors. Sample exports were rendered with installed Microsoft Word and inspected: the full company header is on the first page of each document. Fixed PDFs are two pages for move-in and house rules, four for AC tenancy, three for non-AC tenancy, and three for the complete offer. Word pagination varies with entered text.

### Files

- `backend/template_docx.py`: original DOCX field mapping
- `backend/offer_docx.py`: editable offer placeholders; `scripts/build_offer_pdf.py`: offer PDF mapping
- `backend/converted_pdf.py`: converted PDF field filling
- `agreements/pdf/`: checked PDF backgrounds and field maps
- `scripts/build_pdf_maps.py`: offline Word export and map rebuilding
- `backend/models.py`: input validation
- `backend/tests/`: automated checks
- `frontend/src/`: responsive staff interface
- `TEMPLATE_MAPPING.md`: template preservation details and hashes

Changing source structure requires reviewing the field mapping and rerunning checks. Templates are read from disk at generation time. The server exposes only the built frontend and API, not the source folders.

The Linux Docker image and Vercel support PDF previews and downloads for every document type, along with Original formats.

## Staff access

The website and all API endpoints require the shared staff password. There is no public registration. The initial password for this installation is in `.local/initial-login.txt`; save it in your password manager and remove that file. Only share it with authorised staff.

Set or change the password on the host computer:

```powershell
.\.venv\Scripts\python.exe -m backend.setup_access
```

The prompt hides the password. Password changes revoke existing sessions on their next request. Sessions expire after eight hours or when the server restarts. Sign out revokes the current session. Five failed attempts from one client address trigger a 15-minute wait. The password is stored as a salted PBKDF2 hash in `.local/auth.json`; missing/invalid configuration blocks access. `.local/` is excluded from source control and Docker builds. Never publish its contents.

Run one backend worker: sessions and attempt limits are held in memory. For Docker, configure the password file outside the image and mount it at `/app/.local/auth.json`, readable by the app user, or set `NEST_AUTH_FILE` to a mounted file. Fresh installations prompt for a password through `start.ps1`.

This remains a local-network app. Authentication does not create a VPN or firewall restriction. For access beyond your trusted Wi-Fi, use a private VPN or an HTTPS deployment with access controls; do not forward this plain HTTP port to the internet. HTTPS requests receive Secure session cookies; set `NEST_SECURE_COOKIE=1` when using an HTTPS reverse proxy. Configure trusted proxy headers only for that proxy. Do not use the Angular development server for staff access; use the Python-served production build on port 8000.

Saved property addresses are in `.local/addresses.json` on the server. No tenant records are stored. Expiry shortcuts end the day before the anniversary; when the anniversary day is missing (for example August 31 to February), expiry uses the target month’s last day. Old drafts omit the removed fee fields when loaded.

## Vercel deployment

See [DEPLOYMENT.md](DEPLOYMENT.md) for the combined Angular/FastAPI deployment, Upstash setup, password-hash export, and address migration. On Vercel, Redis stores sessions, rate limits and shared address options. The local Windows setup remains available. The converted templates and field maps are included for full PDF generation.
