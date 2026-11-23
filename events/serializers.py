from datetime import timezone as dt_timezone

from django.utils import timezone
from rest_framework import serializers

from .models import Category, Event, validate_web_link


def utc_datetime(**kwargs):
    """A datetime field that always speaks UTC, like the database.

    The frontend converts to the viewer's local time. A value sent without an
    offset is read as UTC, so always send one, like 2026-12-01T18:00:00Z.
    """
    return serializers.DateTimeField(default_timezone=dt_timezone.utc, **kwargs)


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ["id", "name"]


class EventSerializer(serializers.ModelSerializer):
    """What the public calendar sees.

    Never includes manage_key, ref_number or submitter_email.
    """

    start_at = utc_datetime(read_only=True)
    end_at = utc_datetime(read_only=True)
    categories = CategorySerializer(many=True, read_only=True)
    submitter_name = serializers.SerializerMethodField()

    class Meta:
        model = Event
        fields = [
            "id",
            "title",
            "start_at",
            "end_at",
            "event_link",
            "attendance_mode",
            "description",
            "categories",
            "submitter_name",
            "status",
        ]

    def get_submitter_name(self, event):
        return event.submitter_name or "Anonymous"


class EventCreateSerializer(serializers.ModelSerializer):
    """Validates a new submission. Status is never taken from the request."""

    categories = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=Category.objects.all(),
        allow_empty=False,
        error_messages={"empty": "Choose at least one category."},
    )

    start_at = utc_datetime()
    end_at = utc_datetime(required=False, allow_null=True)
    event_link = serializers.URLField(max_length=500, validators=[validate_web_link])

    class Meta:
        model = Event
        fields = [
            "title",
            "submitter_email",
            "submitter_name",
            "start_at",
            "end_at",
            "event_link",
            "attendance_mode",
            "description",
            "categories",
        ]

    def validate_start_at(self, value):
        # Only checked on submit, not in the model, so the admin can still
        # approve an event whose start time has slipped past.
        if value <= timezone.now():
            raise serializers.ValidationError("The event start must be in the future.")
        return value

    def validate(self, attrs):
        end_at = attrs.get("end_at")
        if end_at and end_at <= attrs["start_at"]:
            raise serializers.ValidationError(
                {"end_at": "The end time must be after the start time."}
            )
        return attrs


class EventCreatedSerializer(EventSerializer):
    """The response to a successful submit. Adds the reference number."""

    class Meta(EventSerializer.Meta):
        fields = EventSerializer.Meta.fields + ["ref_number"]


class EventManageSerializer(serializers.ModelSerializer):
    """What the owner sees through their secret link.

    The owner already knows their own email, name and reference number, so
    these are included. The manage key itself is never sent back.
    """

    start_at = utc_datetime(read_only=True)
    end_at = utc_datetime(read_only=True)
    categories = CategorySerializer(many=True, read_only=True)

    class Meta:
        model = Event
        fields = [
            "id",
            "ref_number",
            "title",
            "submitter_email",
            "submitter_name",
            "start_at",
            "end_at",
            "event_link",
            "attendance_mode",
            "description",
            "categories",
            "status",
        ]


class EventManageUpdateSerializer(EventCreateSerializer):
    """Validates an edit. Only some fields can change.

    The email, reference number and status are not editable here. Used with
    partial=True, so the owner can send just the fields they changed.
    """

    class Meta(EventCreateSerializer.Meta):
        fields = [f for f in EventCreateSerializer.Meta.fields if f != "submitter_email"]

    def validate_start_at(self, value):
        # An unchanged start time is fine even if it has passed. Otherwise
        # nobody could fix the description of an event that already started.
        if self.instance is not None and value == self.instance.start_at:
            return value
        return super().validate_start_at(value)

    def validate(self, attrs):
        # With a partial edit, compare against the saved values for any
        # field that was not sent.
        start_at = attrs.get("start_at", self.instance.start_at)
        end_at = attrs["end_at"] if "end_at" in attrs else self.instance.end_at
        if end_at and end_at <= start_at:
            raise serializers.ValidationError(
                {"end_at": "The end time must be after the start time."}
            )
        return attrs

    def changed_fields(self):
        """Names of the validated fields whose value differs from what is saved."""
        changed = []
        for name, value in self.validated_data.items():
            if name == "categories":
                if {c.pk for c in value} != {c.pk for c in self.instance.categories.all()}:
                    changed.append(name)
            elif value != getattr(self.instance, name):
                changed.append(name)
        return changed
