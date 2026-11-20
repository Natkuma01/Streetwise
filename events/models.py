import secrets
import uuid

from django.core.exceptions import ValidationError
from django.core.validators import URLValidator
from django.db import models


# Only web links. Applied to the API field too, because the REST framework
# drops a custom URLValidator when it builds a field from the model.
validate_web_link = URLValidator(schemes=["http", "https"])


def generate_reference_number():
    """Short random code people can quote in an email, like SW-A3F19C2B."""
    return "SW-" + secrets.token_hex(4).upper()


class Category(models.Model):
    name = models.CharField(max_length=80, unique=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "categories"

    def __str__(self):
        return self.name


class Event(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        CANCELLED = "cancelled", "Cancelled"

    class AttendanceMode(models.TextChoices):
        IN_PERSON = "in_person", "In person"
        VIRTUAL = "virtual", "Virtual"

    # Public. Safe to show to the submitter and to quote in an email.
    reference_number = models.CharField(
        max_length=16,
        unique=True,
        editable=False,
        default=generate_reference_number,
    )
    # Secret. Only ever sent in the receipt email. Powers the edit and cancel
    # link, so it must never appear on the site or in the public API.
    manage_key = models.UUIDField(unique=True, editable=False, default=uuid.uuid4)

    title = models.CharField(max_length=200)
    submitter_email = models.EmailField()
    submitter_name = models.CharField(max_length=120, blank=True)

    # Stored in UTC. The frontend shows the viewer's local time.
    start_at = models.DateTimeField()
    end_at = models.DateTimeField(null=True, blank=True)

    event_link = models.URLField(
        max_length=500,
        validators=[validate_web_link],
    )
    attendance_mode = models.CharField(max_length=10, choices=AttendanceMode.choices)
    description = models.TextField(blank=True)
    categories = models.ManyToManyField(Category, related_name="events")

    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    # Set by the 24-hour reminder job so it never reminds twice (SSP-21).
    reminder_sent_at = models.DateTimeField(null=True, blank=True, editable=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["start_at", "title"]

    def __str__(self):
        return f"{self.title} ({self.reference_number})"

    def clean(self):
        super().clean()
        if self.start_at and self.end_at and self.end_at <= self.start_at:
            raise ValidationError({"end_at": "The end time must be after the start time."})
