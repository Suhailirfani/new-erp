from django.core.management.base import BaseCommand
from datetime import date
from fees.services import generate_monthly_fees_for_all


class Command(BaseCommand):
    help = 'Generate monthly fees (Hostel & Vehicle) for the current month.'

    def add_arguments(self, parser):
        parser.add_argument('--month', type=int, default=None, help='Month (1-12)')
        parser.add_argument('--year', type=int, default=None, help='Year (e.g. 2026)')

    def handle(self, *args, **options):
        today = date.today()
        month = options['month'] or today.month
        year = options['year'] or today.year

        billing_month = date(year, month, 1)
        self.stdout.write(f"Generating fees for {billing_month.strftime('%B %Y')}...")

        try:
            created, updated = generate_monthly_fees_for_all(billing_month)
            self.stdout.write(self.style.SUCCESS(
                f"Done. Created: {created} new fees, Updated: {updated} existing fees."
            ))
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"Error: {e}"))
            raise
