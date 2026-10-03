"""Rebuild all placeholder-based PDFs using Microsoft Word on Windows."""
import argparse
from backend.template_docx import SOURCES
from scripts.placeholder_pdf import build


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--export',action='store_true',help='Export the current Word templates (always required for placeholder mapping).')
    parser.parse_args()
    for key,source in SOURCES.items():
        build(key,source)
    from scripts.build_offer_pdf import build as build_offer
    build_offer()


if __name__=='__main__':
    main()
