"""Offer PDF output uses the editable Word template and its checked PDF map."""
from .offer_docx import values


def fill_offer(details):
    from .converted_pdf import fill_converted
    values(details)  # Retain an automatically assigned invoice on this request object.
    return fill_converted('offer', details)
