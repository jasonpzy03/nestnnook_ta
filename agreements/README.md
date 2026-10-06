# Editing document templates

All six active Word templates use visible `{{field_name}}` placeholders:

- `1. Move in Form - quantity.docx`
- `2. House Rules.docx`
- `3. Room TA_AC.docx`
- `3. Room TA_NOAC.docx`
- `4. Letter of Offer to Rent.docx`
- `Car Park Rental Agreement.docx`

The older move-in file and original offer PDF are reference copies, not generation sources.

## Ordinary edits

Edit fixed wording, headings and labels in Word. Keep each placeholder exactly spelled wherever you want the website to insert a value. You can move a table row or change its label: the field is identified by its placeholder, not the row number or old sample text. Keep the existing paragraphs and PDF-space bookmarks when possible. Company placeholders use the website's company settings. Edit those settings to change the inserted company details.

Word downloads fill the saved template immediately. PDF generation uses a checked conversion, so after editing run this on Windows with Microsoft Word installed:

```powershell
.venv/Scripts/python.exe -m scripts.build_pdf_maps --export
```

For only the offer:

```powershell
.venv/Scripts/python.exe -m scripts.build_offer_pdf
```

Preview every page using realistic tenant information. Then commit the Word templates, their updated `agreements/pdf/*.pdf` and `*.json` files, and redeploy. Vercel does not need Word. It rejects stale PDF maps rather than generating old wording.

## Fields

Use double braces around each name, e.g. `{{tenant_name}}`.

| Group | Fields |
| --- | --- |
| Tenant | `tenant_name`, `tenant_id`, `nationality`, `phone`, `email`, `occupation`, `employer`, `vehicle` |
| Emergency contact | `emergency_name`, `emergency_id`, `emergency_relationship`, `emergency_phone` |
| Guardian | `guardian_name`, `guardian_id`, `guardian_date` (dash when no guardian is supplied) |
| Property | `property` (unit number), `room`, `address`, `property_address` (address with unit prefix) |
| Dates | `agreement_date`, `start_date`, `end_date`, `tenure` |
| AC allowance | `aircon_kwh` (electricity allowance, including decimals; defaults to 40; add ` kWh` after the placeholder) |
| Payments | `rent`, `parking`, `security_deposit`, `access_deposit`, `advance_rent`, `agreement_fee`, `total` |
| Tenancy rental label | `rental_label` — shows `Rental (Extend 6 months @RM …)` for new tenants with exactly six months, using monthly rent minus RM100; otherwise shows `Rental` |
| Offer | `reference` (automatic invoice number when blank), `special_conditions` |
| Move-in | `meter_reading`, `drawer_with`, `drawer_without` |
| Company | `company.name`, `company.registration`, `company.address`, `company.phone`, `company.contact`, `company.email`, `company.account_name`, `company.account_number`, `company.bank` |
| Car park | `carpark_lot`, `carpark_address`, `carpark_agreement_date`, `carpark_start_date`, `carpark_end_date`, `carpark_tenure`, `carpark_rent`, `carpark_deposit`, `carpark_earnest_deposit` |

The car park workflow shares tenant identity and company settings, with its own dates, address selection, Lot, rental and deposit. Monthly rental defaults to RM300. Earnest deposit is calculated from the car park rental and commencement date, including that day through month-end, rounded to cents. Lot initially uses the current TA unit if available and remains editable. Addresses use the existing saved list. PDF names use `<lot>_CPA.pdf`. The original supplied document is backed up in `backups/before-carpark-template-20261006/`.

Rebuild only the car park PDF after editing its Word template:

```powershell
.venv/Scripts/python.exe -c "from scripts.placeholder_pdf import build; from backend.template_docx import SOURCES; build('carpark', SOURCES['carpark'])"
```

Amounts include RM; zero/empty amounts become a dash. Dates retain the existing document-specific format. Entered values are inserted as text, never interpreted as another placeholder. Placeholders split across Word formatting runs are supported. Unknown names produce an error.

The AC allowance is editable under **Tenancy & payments** when an AC tenancy agreement is selected. Zero is a valid allowance and prints as `0 kWh`. Saved drafts retain the allowance; older drafts default to 40. The AC and non-AC templates include the added `company.name` clause and signature placeholders, with PDF mappings and bold emphasis preserved. A backup from before this update is in `backups/before-tenancy-kwh-20261004/`.

### Inventory fields

Short names fit the narrow inventory columns: `{{q1}}` is quantity, `{{g1}}` is good condition, `{{b1}}` is broken, and `{{r1}}` is remarks. The suffix identifies the item, regardless of where its row is moved.

| Suffix | Item |
| --- | --- |
| 0 | Overall room condition (`q0` is always a dash) |
| 1 | Bedframe / Divan |
| 2 | Mattress |
| 3 | Pillow |
| 4 | Makeup table |
| 5 | Chair |
| 6 | Plant decor |
| 7 | Curtain |
| 8 | Wardrobe |
| 9 | Wall decor frame |
| 10 | Rubbish bin |
| 11 | Blanket |
| 12 | Mattress cover |
| 13 | Air conditioner |
| 14 | Air conditioner remote |
| 15 | Ceiling fan |
| 16 | Fan remote |
| 17 | Access card |
| 18 | Room key |
| 19 | Main door key |

Missing inventory entries default to quantity 1 / Good. Unsupplied items use dashes. Fair condition is included in remarks. Drawer choices use `[X]` and `[ ]`, filled from their placeholders. Both the modern and legacy copies of Word text boxes are filled. Some narrow cells compress placeholder text for editing; the filler removes that compression for actual values.

## PDF layout metadata

Field values no longer depend on sample text or table row positions. PDF output still needs a bounded space for each variable paragraph, because Vercel cannot run Word to reflow pages.

The four migrated templates keep this space in Word bookmarks named `NNF_<id>_<width>_<height>_<size>_<align>_<font>`. Width and height are in twips (20 per point), alignment is 0=left, 1=center, 2=right. The size component is legacy spacing metadata in half-points; it no longer sets the output font size. Font codes: B=body, D=bold, K=bank, S=header sans, T=header serif. During rebuilding, temporary marker text locates the paragraph; table cells provide their current boundaries. The resulting map stores the placeholder expression and PDF rectangle, not a sample name or fixed row index.

Change a field's font size directly in Word, selecting the whole placeholder (or the full line for a line containing labels and placeholders). Rebuild the PDFs after saving. Both builders read the effective font size from Word's PDF export, including sizes inherited from styles. Header fields also follow the Word paragraph alignment, keep the chosen size exactly and report an overflow if the text cannot fit. Other fields start at the Word size and may shrink to fit long entered values. A mapped paragraph uses one font size; mixed sizes within that paragraph are not reproduced separately. Font family and reserved field space still use the mapping metadata, so this is not a full Word layout engine.

Keep the NNF bookmark when moving or editing a variable paragraph. Adding a new variable paragraph requires a unique bookmark and enough reserved space. Static wording needs no bookmark. The offer retains its `OfferSlot_<id>_L<lines>` bookmarks for the same purpose. Its optional enclosure stays inside the `offer_aml` content control with its own page break and ENCLOSURE heading.

Offer fields inside Word text boxes are supported. Keep the OfferSlot bookmark on the paragraph containing the field; the outer paragraph holding the text box needs no bookmark. If a bookmarked paragraph is split into several paragraphs, adjust its reserved line count to cover only the paragraph containing the field. Keep the entire enclosure, including its text box and preceding section break, inside `offer_aml` so the website can omit it from Word downloads.

Changes to columns, page breaks, fonts, field space or large amounts of wording need a fresh visual check. Word output reflows normally; PDF output reports a field overflow instead of truncating content.

## Restore the previous method

The complete local backup is `backups/before-all-placeholders-2026-10-03-4063aec/`. It includes the saved templates, old filling code, builders, PDF copies/maps, tests and frontend source. It excludes credentials and staff data.

Stop the app and close the templates in Word, then run from the project root:

```powershell
powershell -ExecutionPolicy Bypass -File backups/before-all-placeholders-2026-10-03-4063aec/restore.ps1
.\start.ps1
```

The restore script verifies checksums and saves files it overwrites into another backup folder. For Vercel, commit and redeploy the restored files. Keep a separate copy of the backup folder: `backups/` is excluded from Git and deployment.

The TA **Tenancy type** selector defaults to **New tenant** (`tenancy_type: new`). Choose **Renewal** (`renewal`) to omit the extension note for any tenure. The TA monthly car park rental (`parking`) remains independent of the car park agreement rental (`carpark_rent`).
