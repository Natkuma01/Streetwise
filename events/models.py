from django.core.validators import URLValidator
from django.db import models


class Event(models.Model):
    title = models.CharField(max_length=180)
    start_at = models.DateTimeField()
    end_at = models.DateTimeField()
    event_url = models.URLField(max_length=1000, validators=[URLValidator()])
    categories = models.JSONField(default=list)
    location = models.CharField(max_length=240, blank=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["start_at", "title"]

    def __str__(self):
        return self.title

