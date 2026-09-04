from django.apps import AppConfig
import threading
import logging

logger = logging.getLogger(__name__)


def _start_monthly_fee_scheduler():
    """
    Background thread: checks periodically and auto-generates monthly recurring fees on the 1st of each month.
    """
    import time
    from datetime import date

    def run():
        time.sleep(30)
        last_run_month = None
        while True:
            try:
                today = date.today()
                if today.day == 1 and last_run_month != (today.year, today.month):
                    logger.info(f"[Auto Fee] Generating monthly fees for {today.strftime('%B %Y')}...")
                    from fees.services import batch_generate_monthly_fees
                    billing_month = date(today.year, today.month, 1)
                    res = batch_generate_monthly_fees(billing_month)
                    last_run_month = (today.year, today.month)
                    logger.info(f"[Auto Fee] Done — Generated {res['total_count']} items.")
            except Exception as e:
                logger.error(f"[Auto Fee] Error: {e}")
            time.sleep(3600)

    thread = threading.Thread(target=run, daemon=True, name="MonthlyFeeAutoGenerator")
    thread.start()


class FeesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'fees'

    def ready(self):
        import fees.signals
        import sys
        SKIP_COMMANDS = {
            'migrate', 'makemigrations', 'collectstatic', 'test', 'check',
            'createsuperuser', 'dbshell', 'dumpdata', 'loaddata', 'flush',
            'generate_monthly_fees', 'help', 'shell', 'inspectdb',
        }
        current_cmd = sys.argv[1] if len(sys.argv) > 1 else ''
        if current_cmd not in SKIP_COMMANDS:
            _start_monthly_fee_scheduler()
