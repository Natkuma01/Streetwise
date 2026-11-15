import hashlib
import json
import re
from datetime import date, datetime, time
from urllib.parse import parse_qs, urlparse
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.validators import URLValidator, validate_email
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.html import strip_tags
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt

from .models import Event, Video

CATEGORIES = [
    "Tech", "Finance", "Marketing", "Business", "Entrepreneurship",
    "Education", "Arts & Culture", "Community", "Career", "Others",
]

YOUTUBE_HOSTS = {
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "music.youtube.com",
}
YOUTUBE_SHORT_HOSTS = {"youtu.be", "www.youtu.be"}
YOUTUBE_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{11}$")
HTTP_URL_VALIDATOR = URLValidator(schemes=["http", "https"])
EVENT_RATE_LIMIT = 5
EVENT_RATE_WINDOW_SECONDS = 10 * 60
EVENT_TEXT_LIMITS = {
    "title": 180,
    "location": 240,
    "description": 2000,
    "submitter_name": 120,
    "submitter_email": 254,
    "event_url": 1000,
}


def serialize_event(event):
    return {
        "id": event.id,
        "reference": event.reference,
        "title": event.title,
        "start_at": event.start_at.isoformat(),
        "end_at": event.end_at.isoformat() if event.end_at else None,
        "time_zone": event.time_zone,
        "event_url": event.event_url,
        "categories": event.categories,
        "location": event.location,
        "description": event.description,
        "status": event.status,
    }


def parse_datetime(value):
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed, timezone.get_current_timezone())
    return parsed


def sanitize_text(value):
    if not isinstance(value, str):
        raise TypeError
    return " ".join(strip_tags(value).split())


def validate_length(errors, field, value, label):
    if len(value) > EVENT_TEXT_LIMITS[field]:
        errors[field] = f"{label} must be {EVENT_TEXT_LIMITS[field]} characters or fewer."


def build_event_datetime(event_date, event_time, time_zone_name):
    zone = ZoneInfo(time_zone_name)
    return datetime.combine(
        date.fromisoformat(event_date),
        time.fromisoformat(event_time),
        tzinfo=zone,
    )


def event_submission_fingerprint(title, start_at):
    normalized = f"{title.casefold()}|{start_at.astimezone(timezone.utc).isoformat()}"
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def event_submission_is_rate_limited(request):
    remote_address = request.META.get("REMOTE_ADDR", "unknown")
    key = f"event-submit:{hashlib.sha256(remote_address.encode('utf-8')).hexdigest()}"
    if cache.add(key, 1, timeout=EVENT_RATE_WINDOW_SECONDS):
        return False
    try:
        count = cache.incr(key)
    except ValueError:
        cache.set(key, 1, timeout=EVENT_RATE_WINDOW_SECONDS)
        return False
    return count > EVENT_RATE_LIMIT


def extract_youtube_id(value):
    try:
        parsed = urlparse(value)
    except (TypeError, ValueError):
        return None
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return None

    host = parsed.hostname.lower()
    candidate = None
    if host in YOUTUBE_SHORT_HOSTS:
        candidate = parsed.path.strip("/").split("/")[0]
    elif host in YOUTUBE_HOSTS:
        path_parts = [part for part in parsed.path.split("/") if part]
        if parsed.path.rstrip("/") == "/watch":
            candidate = parse_qs(parsed.query).get("v", [None])[0]
        elif len(path_parts) >= 2 and path_parts[0] in {"embed", "shorts", "live"}:
            candidate = path_parts[1]

    return candidate if candidate and YOUTUBE_ID_PATTERN.fullmatch(candidate) else None


def serialize_video(video):
    return {
        "id": video.id,
        "reference": video.reference,
        "youtube_url": video.youtube_url,
        "youtube_id": video.youtube_id,
        "categories": video.categories,
        "submitter_name": video.submitter_name,
        "description": video.description,
        "status": video.status,
    }


@csrf_exempt
@require_http_methods(["GET", "POST"])
def event_list(request):
    if request.method == "GET":
        events = Event.objects.filter(
            status__in=[
                Event.Status.PUBLISHED,
                Event.Status.PENDING,
                Event.Status.CANCELLED,
            ]
        )
        start = request.GET.get("start")
        end = request.GET.get("end")
        if start:
            window_start = parse_datetime(start)
            events = events.filter(
                Q(end_at__gte=window_start)
                | Q(end_at__isnull=True, start_at__gte=window_start)
            )
        if end:
            events = events.filter(start_at__lt=parse_datetime(end))
        return JsonResponse({"events": [serialize_event(event) for event in events]})

    if event_submission_is_rate_limited(request):
        return JsonResponse(
            {"errors": {"form": "Too many submissions were sent from this connection. Please try again in 10 minutes."}},
            status=429,
        )

    try:
        data = json.loads(request.body)
        title = sanitize_text(data.get("title", ""))
        event_url = sanitize_text(data.get("event_url", ""))
        location = sanitize_text(data.get("location", ""))
        description = sanitize_text(data.get("description", ""))
        submitter_name = sanitize_text(data.get("submitter_name", ""))
        submitter_email = sanitize_text(data.get("submitter_email", "")).lower()
        time_zone_name = sanitize_text(data.get("time_zone", ""))
        categories = data.get("categories", [])

        errors = {}
        if not title:
            errors["title"] = "Please add an event title."
        validate_length(errors, "title", title, "Event title")
        validate_length(errors, "event_url", event_url, "Organizer/source link")
        validate_length(errors, "location", location, "Location or meeting link")
        validate_length(errors, "description", description, "Description")
        validate_length(errors, "submitter_name", submitter_name, "Submitter name")
        validate_length(errors, "submitter_email", submitter_email, "Submitter email")

        if event_url:
            try:
                HTTP_URL_VALIDATOR(event_url)
            except ValidationError:
                errors["event_url"] = "Add a valid http or https organizer/source link."
        if location and ("://" in location or location.lower().startswith("www.")):
            try:
                HTTP_URL_VALIDATOR(location)
            except ValidationError:
                errors["location"] = "Add a complete http or https meeting link, or enter a physical location."
        if submitter_email:
            try:
                validate_email(submitter_email)
            except ValidationError:
                errors["submitter_email"] = "Add a valid email address or leave this field blank."

        if not categories or not isinstance(categories, list):
            errors["categories"] = "Choose at least one category."
        elif any(category not in CATEGORIES for category in categories):
            errors["categories"] = "One or more categories are not recognized."
        categories = list(dict.fromkeys(categories)) if isinstance(categories, list) else []

        if not data.get("date"):
            errors["date"] = "Choose an event date."
        if not data.get("start_time"):
            errors["start_time"] = "Add a start time."
        if not time_zone_name:
            errors["time_zone"] = "Choose a time zone."

        start_at = None
        end_at = None
        if data.get("date") and data.get("start_time") and time_zone_name:
            try:
                start_at = build_event_datetime(data["date"], data["start_time"], time_zone_name)
            except (TypeError, ValueError):
                errors["date"] = "Choose a valid event date and start time."
            except ZoneInfoNotFoundError:
                errors["time_zone"] = "Choose a recognized time zone."

        if start_at and start_at <= timezone.now():
            errors["date"] = "Choose a future event date and time."

        if data.get("end_time") and start_at:
            try:
                end_at = build_event_datetime(data["date"], data["end_time"], time_zone_name)
                if end_at <= start_at:
                    errors["end_time"] = "End time must be after start time."
            except (TypeError, ValueError):
                errors["end_time"] = "Add a valid end time or leave it blank."
            except ZoneInfoNotFoundError:
                errors["time_zone"] = "Choose a recognized time zone."

        if errors:
            return JsonResponse({"errors": errors}, status=400)

        fingerprint = event_submission_fingerprint(title, start_at)
        duplicate = Event.objects.filter(submission_fingerprint=fingerprint).first()
        if duplicate:
            return JsonResponse(
                {"errors": {"form": f"This event appears to have already been submitted. Reference: {duplicate.reference}"}},
                status=409,
            )

        try:
            with transaction.atomic():
                event = Event.objects.create(
                    title=title,
                    start_at=start_at,
                    end_at=end_at,
                    time_zone=time_zone_name,
                    event_url=event_url,
                    categories=categories,
                    location=location,
                    description=description,
                    submitter_name=submitter_name,
                    submitter_email=submitter_email,
                    submission_fingerprint=fingerprint,
                    status=Event.Status.PENDING,
                )
        except IntegrityError:
            duplicate = Event.objects.get(submission_fingerprint=fingerprint)
            return JsonResponse(
                {"errors": {"form": f"This event appears to have already been submitted. Reference: {duplicate.reference}"}},
                status=409,
            )
        return JsonResponse({"event": serialize_event(event)}, status=201)
    except (KeyError, TypeError, json.JSONDecodeError):
        return JsonResponse({"errors": {"form": "Please check the submission fields and try again."}}, status=400)


@require_http_methods(["GET"])
def category_list(request):
    return JsonResponse({"categories": CATEGORIES})


@require_http_methods(["GET"])
def event_detail(request, event_id):
    event = get_object_or_404(
        Event.objects.filter(
            status__in=[
                Event.Status.PUBLISHED,
                Event.Status.PENDING,
                Event.Status.CANCELLED,
            ]
        ),
        pk=event_id,
    )
    return JsonResponse({"event": serialize_event(event)})


@csrf_exempt
@require_http_methods(["GET", "POST"])
def video_list(request):
    if request.method == "GET":
        videos = Video.objects.filter(status=Video.Status.PUBLISHED)
        return JsonResponse({"videos": [serialize_video(video) for video in videos]})

    try:
        data = json.loads(request.body)
        youtube_url = data.get("youtube_url", "").strip()
        youtube_id = extract_youtube_id(youtube_url)
        categories = data.get("categories", [])

        errors = {}
        if not youtube_id:
            errors["youtube_url"] = "Add a valid YouTube video link."
        if not categories or not isinstance(categories, list):
            errors["categories"] = "Choose at least one category."
        elif any(category not in CATEGORIES for category in categories):
            errors["categories"] = "One or more categories are not recognized."
        if errors:
            return JsonResponse({"errors": errors}, status=400)

        video = Video.objects.create(
            youtube_url=youtube_url,
            youtube_id=youtube_id,
            categories=list(dict.fromkeys(categories)),
            submitter_name=data.get("submitter_name", "").strip(),
            description=data.get("description", "").strip(),
        )
        return JsonResponse({"video": serialize_video(video)}, status=201)
    except (AttributeError, TypeError, json.JSONDecodeError):
        return JsonResponse({"errors": {"form": "Please check your submission and try again."}}, status=400)

