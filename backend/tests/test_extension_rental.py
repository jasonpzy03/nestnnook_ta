import pytest
from backend.models import Details
from backend.placeholders import fields_for


@pytest.mark.parametrize('aircon', [True, False])
@pytest.mark.parametrize('start,end,expected', [
    ('2026-10-17','2027-04-16',True),
    ('2026-08-31','2027-02-28',True),
    ('2023-08-31','2024-02-29',True),
    ('2026-10-17','2027-10-16',False),
    ('2026-10-17','2027-04-15',False),
    ('2026-10-17','2027-04-17',False),
])
def test_only_exact_six_months_get_extension(start,end,expected,aircon):
    d=Details(start_date=start,end_date=end,rent='1200.50',aircon=aircon)
    assert fields_for('tenancy',d)['rental_label'] == (
        'Rental (Extend 6 months @RM 1,100.50)' if expected else 'Rental')
    assert d.rent == 1200.50


def test_missing_dates_have_no_extension():
    assert fields_for('tenancy',Details())['rental_label']=='Rental'
