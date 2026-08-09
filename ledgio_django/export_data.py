import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ledgio_project.settings")
django.setup()

from django.core.management import call_command

with open("data.json", "w", encoding="utf-8") as f:
    call_command(
        "dumpdata",
        natural_foreign=True,
        natural_primary=True,
        exclude=["auth.permission", "contenttypes"],
        stdout=f,
    )

print("✅ Data exported successfully to data.json")