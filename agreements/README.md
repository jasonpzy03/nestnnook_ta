# Editing the letter of offer

Open **4. Letter of Offer to Rent.docx** in Microsoft Word. This is now the website's offer source. The original `letter of offer to rent.pdf` is retained for reference and is no longer used to generate offers.

You can edit fixed wording, headings, payment labels, logo, and layout. Keep the `{{...}}` fields wherever the website should insert information. For example, `{{tenant_name}}` becomes the tenant's name. Company fields use the company settings entered in the website.

Supported fields:

- `tenant_name`, `tenant_id`, `property` (unit number), `room`, `reference` (invoice number), `special_conditions`
- `agreement_date`, `start_date`, `end_date`, `tenure`
- `rent`, `security_deposit`, `advance_rent`, `access_deposit`, `agreement_fee`, `total`
- `company.name`, `company.registration`, `company.address`, `company.phone`, `company.contact`, `company.email`, `company.bank`, `company.account_name`, `company.account_number`

Wrap each field in double braces, e.g. `{{rent}}`. Word can split a field across formatting runs; the filler still recognizes it. Unknown fields produce an error. Blank values become a dash. An empty invoice number is generated automatically.

The enclosure is inside a Word content control tagged `offer_aml`. Keep that control so the website can omit the enclosure when requested.

## Refresh PDF output after edits

Word downloads use the edited file immediately on the running installation. Vercel PDF generation uses a checked conversion of that file, so after saving changes run this from the project root on Windows with Microsoft Word installed:

```powershell
.venv/Scripts/python.exe -m scripts.build_offer_pdf
```

This updates `agreements/pdf/offer.pdf` and `agreements/pdf/offer.json`. Preview an offer with sample details, check every page, then commit the Word file and both generated files and redeploy. The website refuses to generate an offer PDF when these files no longer match, rather than using old wording.

The existing full rebuild command also refreshes the offer:

```powershell
.venv/Scripts/python.exe -m scripts.build_pdf_maps --export
```

PDF fields have reserved space, like the other documents. Each paragraph containing fields has a Word bookmark named `OfferSlot_<number>_L<lines>`. Keep those bookmarks when editing. If adding a new variable paragraph, give it a unique bookmark with enough reserved lines and rebuild. Keep the enclosure on its own page and its `ENCLOSURE` heading. Changes to column widths, font sizes, or page breaks need a fresh visual check. Word downloads reflow with the entered text; PDFs report an error if a value cannot fit.
