from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("events", "0002_starting_categories"),
    ]

    operations = [
        migrations.RenameField(
            model_name="event",
            old_name="reference_number",
            new_name="ref_number",
        ),
    ]
