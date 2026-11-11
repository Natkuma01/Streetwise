import json
from datetime import datetime
from urllib.parse import urlparse

from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt

from .models import Event

CATEGORIES = [
    "Tech", "Finance", "Marketing", "Business", "Entrepreneurship",
    "Education", "Arts & Culture", "Community", "Career", "Others",
]


def serialize_event(event):
    return {
        "id": event.id,
        "title": event.title,
        "start_at": event.start_at.isoformat(),
        "end_at": event.end_at.isoformat(),
        "event_url": event.event_url,
        "categories": event.categories,
        "location": event.location,
        "description": event.description,
    }


def parse_datetime(value):
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed, timezone.get_current_timezone())
    return parsed


@csrf_exempt
@require_http_methods(["GET", "POST"])
def event_list(request):
    if request.method == "GET":
        events = Event.objects.all()
        start = request.GET.get("start")
        end = request.GET.get("end")
        if start:
            events = events.filter(end_at__gte=parse_datetime(start))
        if end:
            events = events.filter(start_at__lt=parse_datetime(end))
        return JsonResponse({"events": [serialize_event(event) for event in events]})

    try:
        data = json.loads(request.body)
        title = data.get("title", "").strip()
        event_url = data.get("event_url", "").strip()
        categories = data.get("categories", [])
        start_at = parse_datetime(data["start_at"])
        end_at = parse_datetime(data["end_at"])

        errors = {}
        if not title:
            errors["title"] = "Please add an event title."
        if not event_url or urlparse(event_url).scheme not in {"http", "https"}:
            errors["event_url"] = "Please add a valid event link."
        if not categories or not isinstance(categories, list):
            errors["categories"] = "Choose at least one category."
        elif any(category not in CATEGORIES for category in categories):
            errors["categories"] = "One or more categories are not recognized."
        if end_at <= start_at:
            errors["end_at"] = "End time must be after start time."
        if errors:
            return JsonResponse({"errors": errors}, status=400)

        event = Event.objects.create(
            title=title,
            start_at=start_at,
            end_at=end_at,
            event_url=event_url,
            categories=categories,
            location=data.get("location", "").strip(),
            description=data.get("description", "").strip(),
        )
        return JsonResponse({"event": serialize_event(event)}, status=201)
    except (KeyError, ValueError, TypeError, json.JSONDecodeError):
        return JsonResponse({"errors": {"form": "Please check the required date and time fields."}}, status=400)


@require_http_methods(["GET"])
def category_list(request):
    return JsonResponse({"categories": CATEGORIES})

