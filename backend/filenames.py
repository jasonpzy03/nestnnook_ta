"""Portable filenames for downloaded and shared PDFs."""
import re

DOCUMENT_CODES = {'tenancy': 'TA', 'move_in': 'MIF', 'rules': 'HR', 'offer': 'LOF'}


def pdf_stem(details):
    def part(value):
        return re.sub(r'[^a-zA-Z0-9_-]+', '-', value).strip('-_')[:60] or '-'
    room = part(re.sub(r'^[rR](?=\d)', '', details.room))
    return f'{part(details.property)}_R{room}'


def pdf_filename(kind, details):
    return f'{pdf_stem(details)}_{DOCUMENT_CODES[kind]}.pdf'
