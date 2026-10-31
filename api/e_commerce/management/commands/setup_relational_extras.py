"""
Creates the relational-DB extras the EFREI BDD subject asks for, on top of
the tables already created by `manage.py migrate --database=migration`:
a view, a deliberately-created index, a trigger+function, an extra CHECK
constraint, and the restricted `commerce_app` role the application connects
with at runtime (never the migration/owner role).

Idempotent: safe to run on every container start (uses CREATE OR REPLACE /
IF NOT EXISTS / DROP-then-ADD everywhere).

Must run against the 'migration' database alias (owner role with DDL
rights) -- the 'default' alias (commerce_app) intentionally cannot do DDL.
"""
import os
from pathlib import Path

from django.core.management.base import BaseCommand
from django.db import connections

# The SQL itself lives in docker/init-sql/ (mounted at /init-sql in the api
# container) so the repository has one readable place for every creation
# script. Files are applied in name order.
INIT_SQL_DIR = Path(os.environ.get("INIT_SQL_DIR", "/init-sql"))


class Command(BaseCommand):
    help = "Apply docker/init-sql/*.sql (view/index/trigger/CHECK/restricted role) on top of the Django-migrated schema."

    def handle(self, *args, **options):
        scripts = sorted(INIT_SQL_DIR.glob("*.sql"))
        if not scripts:
            raise FileNotFoundError(f"No .sql script found in {INIT_SQL_DIR}")

        connection = connections["migration"]
        with connection.cursor() as cursor:
            for script in scripts:
                cursor.execute(script.read_text(encoding="utf-8"))
                self.stdout.write(f"setup_relational_extras: applied {script.name}")
            # Role names cannot be bound as parameters, but the password
            # literal can; it is rebuilt from the env on every start so a
            # rotated .env value takes effect.
            cursor.execute(
                "SELECT format('ALTER ROLE commerce_app PASSWORD %%L', %s)",
                [os.environ["POSTGRES_APP_PASSWORD"]],
            )
            cursor.execute(cursor.fetchone()[0])
        self.stdout.write(self.style.SUCCESS(
            "setup_relational_extras: view, index, trigger, constraint and commerce_app role are in place."
        ))
