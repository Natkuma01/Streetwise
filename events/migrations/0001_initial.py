from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies = []
    operations = [
        migrations.CreateModel(
            name="Event",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=180)),
                ("start_at", models.DateTimeField()),
                ("end_at", models.DateTimeField()),
                ("event_url", models.URLField(max_length=1000)),
                ("categories", models.JSONField(default=list)),
                ("location", models.CharField(blank=True, max_length=240)),
                ("description", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={"ordering": ["start_at", "title"]},
        ),
    ]

