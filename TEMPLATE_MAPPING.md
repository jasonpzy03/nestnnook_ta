# Template preservation record

The files below are the source of truth. The generator reads them without modifying them.

| Source | SHA-256 |
| --- | --- |
| 1. Move in Form.docx | `a390bbdf9bbf1933ba2335499ffcee21171cf45c9e308ff69c12337112c34d0a` |
| 2. House Rules.docx | `2f8f47260527a8afd4ee5f5368b0c601d3058f5d878ca9474bd8ad8320a0c640` |
| 3. Room TA_AC.docx | `950f160dbad8f9ae9d2a7ecc6ec99bcc5c7a1253e535e5d566a0b194db42bab6` |
| 3. Room TA_NOAC.docx | `6854aa61aed46d2ca7d774443b937a665edc768ad688c97c309928f0c0e454aa` |
| letter of offer to rent.pdf | `eb42ef0a886e9abd9c9bd5a821c940bd9c4672a2c0cd31eaa5f21cc9986610e6` |

## Word templates

Only word/document.xml changes. All other ZIP member payloads, including styles, numbering, relationships, headers, footers and document settings, are copied unchanged. Paragraph, table, row, cell and section properties are retained. Existing runs supply formatting for inserted values.

Tenancy: fill the first table by existing row label, bank table values, tenant/company signature cells and optional guardian cells. Fixed paragraphs remain, apart from the non-AC landlord company substitution. No payment rows are added.

House rules: replace only the sample tenant name and ID. Original operational contacts and clauses remain.

Move-in: fill registration and emergency tables, inventory DrawingML and VML fallback tables, bank text boxes and signature fields. Remove the sample drawer mark when not applicable; move it to the existing with-drawer box when selected. Existing checkbox glyphs and layout stay in place.

## Offer PDF

The original PDF is opened and text in mapped variable rectangles is redacted and replaced at the original font size and coordinates. The previous logo and officer signature images are removed; the business-card logo is clipped into the original logo space. No page reconstruction. Table lines and other fixed drawings remain unchanged. The third page is retained unless explicitly excluded. Overlong values are rejected rather than resizing or repaginating the document.

## Verification

Automated tests compare all untouched Word parts, original paragraph/table/cell/section properties and fixed clauses. PDF tests compare page geometry and drawing objects (excluding internal sequence numbers), and check removal of the sample signature. Native Word renders of both tenancy variants and the two forms were visually inspected alongside the source PDFs. QA copies and page images are in tmp/exact-qa; original renders are in tmp/template-reference.

## Requested revisions on 2026-10-02

The active move-in source is `agreements/1. Move in Form - quantity.docx`, derived from the original with a separate Qty column in both embedded table copies. Total width and page geometry remain unchanged. The original was locked and has been retained. Deposit labels now say refundable. Blank optional fields use dashes. Offer payment table keeps its original footprint with ten rows; utilities, transfer fee and other charges are removed, agreement fee is separate. Transfer-fee clause and acknowledgement references are removed; subsequent headings are renumbered and the gap is closed. These are authorised deviations from the earlier preservation record.

Revised move-in template SHA-256: `9f5d79d3974f1aeb078454e0a1292b339ef6396da67d9b373ccf01d982c52341`. The new template has distinct default quantities and Good Condition values; sample damage remarks are cleared.

## Converted PDF templates

`agreements/pdf/` contains Word-exported backgrounds and JSON field maps for AC tenancy, non-AC tenancy, house rules and move-in. Original DOCX files are unchanged by conversion. The backgrounds retain the original pages, fixed clauses, tables and artwork; only mapped text and the sample drawer mark are cleared. Both tenancy agreements retain their room-transfer fee clauses.

At runtime, `backend/converted_pdf.py` reuses the existing DOCX filling logic, reads mapped values from that in-memory XML, and writes them into the PDF. Original fonts are embedded, with a Unicode fallback for names. Text may wrap and shrink to 7 pt within its assigned area; entries that still do not fit are rejected. These are completed, printable PDFs, with data entered through the website.

To rebuild after editing a Word source, install development dependencies and run on Windows with Word installed:

```powershell
.\.venv\Scripts\python.exe -m scripts.build_pdf_maps --export
.\.venv\Scripts\python.exe -m pytest backend/tests -q -p no:cacheprovider
```

Review field coordinates when source layout changes. Render representative filled PDFs and inspect every page before committing the backgrounds and maps together. Source and background SHA-256 checks block generation if either changes without an updated map. Native intermediate exports are in `tmp/pdfs/`; running without `--export` reuses them. The downloadable blank copies in `output/pdf/` include the company details and dash placeholders; raw backgrounds are internal generator assets.
