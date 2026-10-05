"""Portable filenames for downloaded and shared PDFs."""
import re

DOCUMENT_CODES = {'tenancy': 'TA', 'move_in': 'MIF', 'rules': 'HR', 'offer': 'LOF', 'carpark':'CPA'}


def pdf_stem(details):
    def part(value):
        return re.sub(r'[^a-zA-Z0-9_-]+', '-', value).strip('-_')[:60] or '-'
    room = part(re.sub(r'^[rR](?=\d)', '', details.room))
    return f'{part(details.property)}_R{room}'


def pdf_filename(kind, details):
    if kind == 'carpark':
        lot=re.sub(r'[^a-zA-Z0-9_-]+','-',details.carpark_lot).strip('-_')[:60] or '-'
        return f'{lot}_CPA.pdf'
    return f'{pdf_stem(details)}_{DOCUMENT_CODES[kind]}.pdf'
