from django.db import models


class Event(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PUBLISHED = "published", "Published"
        REJECTED = "rejected", "Rejected"
        CANCELLED = "cancelled", "Cancelled"

    title = models.CharField(max_length=180)
    start_at = models.DateTimeField()
    end_at = models.DateTimeField()
    event_url = models.URLField(max_length=1000)
    categories = models.JSONField(default=list)
    location = models.CharField(max_length=240, blank=True)
    description = models.TextField(blank=True)
    status = models.CharField(
        max_length=12,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["start_at", "title"]

    def __str__(self):
        return self.title


class Video(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PUBLISHED = "published", "Published"
        REJECTED = "rejected", "Rejected"

    youtube_url = models.URLField(max_length=1000)
    youtube_id = models.CharField(max_length=11)
    categories = models.JSONField(default=list)
    submitter_name = models.CharField(max_length=120, blank=True)
    description = models.TextField(blank=True)
    status = models.CharField(
        max_length=12,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    @property
    def reference(self):
        return f"SSP-VID-{self.pk:06d}" if self.pk is not None else "SSP-VID-PENDING"

    def __str__(self):
        return self.reference

