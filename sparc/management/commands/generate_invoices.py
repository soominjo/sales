from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.contrib.auth import get_user_model

from sparc.models import TranchePayment, BillingInvoice
from sparc.invoice_views import generate_invoice_number

LEAD_DAYS = 7  # how many days before due date to auto-create invoice

def _get_system_user():
    """Return a system user to tag as preparer; fallback to first superuser."""
    User = get_user_model()
    return User.objects.filter(is_superuser=True).first()

class Command(BaseCommand):
    help = "Automatically create BillingInvoice records for tranches whose expected_date is within LEAD_DAYS and do not yet have an invoice."

    def handle(self, *args, **options):
        today = timezone.now().date()
        target_date = today + timedelta(days=LEAD_DAYS)

        tranches = (
            TranchePayment.objects
            .filter(expected_date__range=(today, target_date), invoices__isnull=True)
            .select_related('tranche_record')
        )

        count = 0
        preparer = _get_system_user()

        for tranche in tranches:
            BillingInvoice.objects.create(
                tranche=tranche,
                invoice_no=generate_invoice_number(),
                due_date=tranche.expected_date,
                unit_price=tranche.expected_amount,
                prepared_by=preparer,
            )
            count += 1

        self.stdout.write(self.style.SUCCESS(f"Generated {count} invoice(s)."))
