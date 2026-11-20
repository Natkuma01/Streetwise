from django.db import migrations

STARTING_CATEGORIES = [
    "Cybersecurity",
    "Finance",
    "Human Resources",
    "Web Developer",
    "Business",
    "Marketing",
    "Data Analyst/Engineer",
    "Others",
]


def add_categories(apps, schema_editor):
    Category = apps.get_model("events", "Category")
    for name in STARTING_CATEGORIES:
        Category.objects.get_or_create(name=name)


class Migration(migrations.Migration):
    dependencies = [("events", "0001_initial")]

    # Reverse is a no-op on purpose: the admin may have edited the list.
    operations = [migrations.RunPython(add_categories, migrations.RunPython.noop)]
