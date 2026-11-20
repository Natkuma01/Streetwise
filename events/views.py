import uuid
from datetime import datetime, time, timedelta, timezone as dt_timezone

from django.conf import settings
from django.utils import timezone
from django.utils.cache import add_never_cache_headers
from django.utils.dateparse import parse_date, parse_datetime
from rest_framework import status
from rest_framework.exceptions import APIException, NotFound, ValidationError
from rest_framework.generics import ListAPIView
from rest_framework.response import Response
from rest_framework.views import APIView

from .emails import send_admin_event_edited_email, send_submission_emails
from .models import Category, Event, generate_reference_number
from .serializers import (
    CategorySerializer,
    EventCreatedSerializer,
    EventCreateSerializer,
    EventManageSerializer,
    EventManageUpdateSerializer,
    EventSerializer,
)
from .throttles import EventSubmitThrottle, ManageThrottle

# Rejected and cancelled events never reach the public calendar.
PUBLIC_STATUSES = [Event.Status.PENDING, Event.Status.APPROVED]

# Name of the hidden spam-trap field. The frontend must render it hidden
# and leave it empty (see docs/api.md).
HONEYPOT_FIELD = "fax_number"


def parse_range_value(name, raw, end_of_day=False):
    """Accept an ISO datetime with offset, or a plain date read as UTC."""
    # Check for a plain date first. Python 3.11+ would otherwise read
    # "2026-12-01" as a datetime with no timezone.
    day = parse_date(raw)
    if day is not None:
        return datetime.combine(day, time.max if end_of_day else time.min, tzinfo=dt_timezone.utc)
    value = parse_datetime(raw)
    if value is None:
        raise ValidationError({name: "Use an ISO date or datetime, like 2026-12-01."})
    if value.tzinfo is None:
        raise ValidationError({name: "Include a timezone offset, like 2026-12-01T00:00:00Z."})
    return value


class CategoryListView(ListAPIView):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    pagination_class = None


class EventListCreateView(APIView):
    def get(self, request):
        events = Event.objects.filter(status__in=PUBLIC_STATUSES).prefetch_related("categories")

        start = request.query_params.get("start")
        end = request.query_params.get("end")
        if start:
            events = events.filter(start_at__gte=parse_range_value("start", start))
        if end:
            events = events.filter(start_at__lte=parse_range_value("end", end, end_of_day=True))

        return Response(EventSerializer(events, many=True).data)

    def get_throttles(self):
        # Only submitting is limited. Reading the calendar is not.
        if self.request.method == "POST":
            return [EventSubmitThrottle()]
        return []

    def post(self, request):
        # Honeypot: real visitors never see this field, so it stays empty.
        # Bots fill in every box they find. We answer with a fake success so
        # the bot thinks it worked and does not try a new trick.
        if isinstance(request.data, dict) and request.data.get(HONEYPOT_FIELD):
            return Response(
                {"status": Event.Status.PENDING, "reference_number": generate_reference_number()},
                status=status.HTTP_201_CREATED,
            )

        serializer = EventCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        event = serializer.save()
        send_submission_emails(event)
        return Response(EventCreatedSerializer(event).data, status=status.HTTP_201_CREATED)


# --- Edit and cancel with the secret link (SSP-20) --------------------------


class LinkExpired(APIException):
    status_code = status.HTTP_410_GONE
    default_detail = "This link has expired."
    default_code = "link_expired"


class NotChangeable(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "This event can no longer be changed."
    default_code = "not_changeable"


class ManageBaseView(APIView):
    """Finds the event from the X-Manage-Key header.

    The key goes in a header, not in the URL, so it never lands in server or
    proxy logs. An unknown key and a malformed key look the same (404), so
    nobody can tell which part of a guess was close.
    """

    throttle_classes = [ManageThrottle]

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        # The responses hold private details. Never let a browser or proxy keep them.
        add_never_cache_headers(response)
        return response

    def get_event(self, request):
        raw = request.headers.get("X-Manage-Key", "").strip()
        try:
            key = uuid.UUID(raw)
        except ValueError:
            raise NotFound() from None
        try:
            event = Event.objects.prefetch_related("categories").get(manage_key=key)
        except Event.DoesNotExist:
            raise NotFound() from None

        # The link works until a few days after the event ends.
        ends = event.end_at or event.start_at
        if timezone.now() > ends + timedelta(days=settings.MANAGE_LINK_GRACE_DAYS):
            raise LinkExpired()
        return event

    @staticmethod
    def ensure_changeable(event):
        if event.status == Event.Status.REJECTED:
            raise NotChangeable("A rejected event can't be changed.")
        if event.status == Event.Status.CANCELLED:
            raise NotChangeable("This event was cancelled and can't be changed.")


class ManageEventView(ManageBaseView):
    def get(self, request):
        event = self.get_event(request)
        return Response(EventManageSerializer(event).data)

    def patch(self, request):
        event = self.get_event(request)
        self.ensure_changeable(event)
        was_approved = event.status == Event.Status.APPROVED

        serializer = EventManageUpdateSerializer(event, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        # Saving with nothing changed must not knock an approved event back
        # to Pending, so only real changes count.
        if serializer.changed_fields():
            # Any change means the admin needs to look again. The reminder
            # clock starts over too.
            event = serializer.save(status=Event.Status.PENDING, reminder_sent_at=None)
            if was_approved:
                send_admin_event_edited_email(event)

        return Response(EventManageSerializer(event).data)


class ManageCancelView(ManageBaseView):
    def post(self, request):
        event = self.get_event(request)
        # Cancelling twice is fine and gives the same answer, so only a
        # rejected event is refused here.
        if event.status == Event.Status.REJECTED:
            self.ensure_changeable(event)
        if event.status != Event.Status.CANCELLED:
            event.status = Event.Status.CANCELLED
            event.save(update_fields=["status", "updated_at"])
        return Response(EventManageSerializer(event).data)
