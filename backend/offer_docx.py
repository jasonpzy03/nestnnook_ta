"""Offer source and compatibility entry points for the shared placeholder engine."""
from .template_docx import ROOT
from .placeholders import TOKEN, fields_for, fill_package

SOURCE = '4. Letter of Offer to Rent.docx'


def values(details):
    return fields_for('offer', details)


def fill_offer_docx(details):
    return fill_package((ROOT/'agreements'/SOURCE).read_bytes(), values(details), details.include_aml)
