from decimal import Decimal
import pytest
from backend.models import Details
from backend.placeholders import fields_for


@pytest.mark.parametrize('start,rent,expected', [
    ('2026-10-17', '1000', '483.87'),
    ('2026-10-01', '1000', '1000.00'),
    ('2026-10-31', '1000', '32.26'),
    ('2026-04-17', '1000', '466.67'),
    ('2026-02-17', '1000', '428.57'),
    ('2028-02-17', '1000', '448.28'),
    ('2026-04-16', '100.01', '50.01'),
    ('2026-10-17', '0', '0.00'),
    (None, '1000', '0'),
])
def test_prorated_rent(start, rent, expected):
    details = Details(start_date=start, rent=rent, advance_rent=999,
                      security_deposit=1000, access_deposit=100, agreement_fee=100)
    assert details.advance_rent == Decimal(expected)
    assert details.total == Decimal(expected) + 1200
    assert fields_for('tenancy', details)['advance_rent'] == (
        'RM'+f'{Decimal(expected):,.2f}' if Decimal(expected) else '-')
