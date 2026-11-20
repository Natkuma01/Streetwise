from datetime import datetime, time, timezone as dt_timezone

from django.utils.dateparse import parse_date, parse_datetime
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.generics import ListAPIView
from rest_framework.response import Response
from rest_framework.views import APIView

from .emails import send_submission_emails
from .models import Category, Event
from .serializers import (
    CategorySerializer,
    EventCreatedSerializer,
    EventCreateSerializer,
    EventSerializer,
)

# Rejected and cancelled events never reach the public calendar.
PUBLIC_STATUSES = [Event.Status.PENDING, Event.Status.APPROVED]


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

    def post(self, request):
        serializer = EventCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        event = serializer.save()
        send_submission_emails(event)
        return Response(EventCreatedSerializer(event).data, status=status.HTTP_201_CREATED)
