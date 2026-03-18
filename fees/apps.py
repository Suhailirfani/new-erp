from django.apps import AppConfig
import threading
import logging

logger = logging.getLogger(__name__)


def _start_monthly_fee_scheduler():
    """
    Background thread: checks every hour and auto-generates monthly fees on the 1st.
    Works in both runserver (dev) and WSGI/uWSGI (PythonAnywhere production).
    """
    import time
    from datetime import date

    def run():
        last_run_month = None
        while True:
            try:
                today = date.today()
                if today.day == 1 and last_run_month != (today.year, today.month):
                    logger.info(f"[Auto Fee] Generating monthly fees for {today.strftime('%B %Y')}...")
                    from fees.services import generate_monthly_fees_for_all
                    billing_month = date(today.year, today.month, 1)
                    created, updated = generate_monthly_fees_for_all(billing_month)
                    last_run_month = (today.year, today.month)
                    logger.info(f"[Auto Fee] Done — Created: {created}, Updated: {updated}")
            except Exception as e:
                logger.error(f"[Auto Fee] Error: {e}")
            time.sleep(3600)  # Check every hour

    thread = threading.Thread(target=run, daemon=True, name="MonthlyFeeAutoGenerator")
    thread.start()
    logger.info("[Auto Fee] Monthly fee auto-scheduler started.")


class FeesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'fees'

    def ready(self):
        import fees.signals

        import sys
        # Start the auto-scheduler in any web-serving context:
        # - 'runserver' (development)
        # - WSGI/uWSGI on PythonAnywhere (sys.argv has no manage.py command)
        # Skip it during management commands like migrate, collectstatic, etc.
        SKIP_COMMANDS = {
            'migrate', 'makemigrations', 'collectstatic', 'test', 'check',
            'createsuperuser', 'dbshell', 'dumpdata', 'loaddata', 'flush',
            'generate_monthly_fees', 'help', 'shell', 'inspectdb',
        }
        current_cmd = sys.argv[1] if len(sys.argv) > 1 else ''
        if current_cmd not in SKIP_COMMANDS:
            _start_monthly_fee_scheduler()
