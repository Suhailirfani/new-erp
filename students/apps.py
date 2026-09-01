from django.apps import AppConfig
from django.db.backends.signals import connection_created
from django.dispatch import receiver


@receiver(connection_created)
def configure_sqlite_performance(sender, connection, **kwargs):
    if connection.vendor == 'sqlite':
        try:
            with connection.cursor() as cursor:
                cursor.execute('PRAGMA journal_mode = WAL;')
                cursor.execute('PRAGMA synchronous = NORMAL;')
                cursor.execute('PRAGMA cache_size = -64000;')  # 64MB RAM cache
                cursor.execute('PRAGMA temp_store = MEMORY;')
                cursor.execute('PRAGMA mmap_size = 268435456;')  # 256MB mmap
        except Exception:
            pass


class StudentsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'students'
