# Editing document templates

All five active Word templates use visible `{{field_name}}` placeholders:

- `1. Move in Form - quantity.docx`
- `2. House Rules.docx`
- `3. Room TA_AC.docx`
- `3. Room TA_NOAC.docx`
- `4. Letter of Offer to Rent.docx`

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
| Payments | `rent`, `parking`, `security_deposit`, `access_deposit`, `advance_rent`, `agreement_fee`, `total` |
| Offer | `reference` (automatic invoice number when blank), `special_conditions` |
| Move-in | `meter_reading`, `drawer_with`, `drawer_without` |
| Company | `company.name`, `company.registration`, `company.address`, `company.phone`, `company.contact`, `company.email`, `company.account_name`, `company.account_number`, `company.bank` |

Amounts include RM; zero/empty amounts become a dash. Dates retain the existing document-specific format. Entered values are inserted as text, never interpreted as another placeholder. Placeholders split across Word formatting runs are supported. Unknown names produce an error.

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

The four migrated templates keep this space in Word bookmarks named `NNF_<id>_<width>_<height>_<size>_<align>_<font>`. Width and height are in twips (20 per point), size is in half-points, alignment is 0=left, 1=center, 2=right. Font codes: B=body, D=bold, K=bank, S=header sans, T=header serif. During rebuilding, temporary marker text locates the paragraph; table cells provide their current boundaries. The resulting map stores the placeholder expression and PDF rectangle, not a sample name or fixed row index.

Keep the NNF bookmark when moving or editing a variable paragraph. Adding a new variable paragraph requires a unique bookmark and enough reserved space. Static wording needs no bookmark. The offer retains its `OfferSlot_<id>_L<lines>` bookmarks for the same purpose. Its optional enclosure stays inside the `offer_aml` content control with its own page break and ENCLOSURE heading.

Changes to columns, page breaks, fonts, field space or large amounts of wording need a fresh visual check. Word output reflows normally; PDF output reports a field overflow instead of truncating content.

## Restore the previous method

The complete local backup is `backups/before-all-placeholders-2026-10-03-4063aec/`. It includes the saved templates, old filling code, builders, PDF copies/maps, tests and frontend source. It excludes credentials and staff data.

Stop the app and close the templates in Word, then run from the project root:

```powershell
powershell -ExecutionPolicy Bypass -File backups/before-all-placeholders-2026-10-03-4063aec/restore.ps1
.\start.ps1
```

The restore script verifies checksums and saves files it overwrites into another backup folder. For Vercel, commit and redeploy the restored files. Keep a separate copy of the backup folder: `backups/` is excluded from Git and deployment.
