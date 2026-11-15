import json
from datetime import datetime, timedelta

from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone

from .models import Event, Video


class EventApiTests(TestCase):
    def setUp(self):
        cache.clear()

    def make_event(self, *, title="Community event", status=Event.Status.PUBLISHED, start_at=None):
        start_at = start_at or timezone.make_aware(datetime(2026, 11, 18, 18, 0))
        return Event.objects.create(
            title=title,
            start_at=start_at,
            end_at=start_at + timedelta(hours=1),
            event_url="https://example.com/event",
            categories=["Tech", "Education"],
            status=status,
        )

    def valid_payload(self, **overrides):
        payload = {
            "title": "A useful NYC talk",
            "date": (timezone.localdate() + timedelta(days=7)).isoformat(),
            "start_time": "18:00",
            "end_time": "19:30",
            "time_zone": "America/New_York",
            "event_url": "https://example.com/event",
            "categories": ["Tech", "Education"],
            "location": "Online",
            "description": "An open community lecture.",
            "submitter_name": "Taylor",
            "submitter_email": "taylor@example.com",
        }
        payload.update(overrides)
        return payload

    def post_event(self, payload=None):
        return self.client.post(
            "/api/events/",
            json.dumps(self.valid_payload() if payload is None else payload),
            content_type="application/json",
        )

    def test_valid_submission_is_saved_once_as_pending_with_reference(self):
        payload = self.valid_payload()
        response = self.post_event(payload)

        self.assertEqual(response.status_code, 201)
        self.assertEqual(Event.objects.count(), 1)
        event = Event.objects.get()
        self.assertEqual(event.status, Event.Status.PENDING)
        self.assertEqual(event.time_zone, "America/New_York")
        self.assertEqual(event.submitter_name, "Taylor")
        self.assertEqual(event.submitter_email, "taylor@example.com")
        self.assertEqual(response.json()["event"]["reference"], f"SSP-EVT-{event.id:06d}")

        response = self.client.get("/api/events/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["events"][0]["title"], payload["title"])

    def test_optional_fields_can_be_blank(self):
        payload = {
            **self.valid_payload(),
            "end_time": "",
            "event_url": "",
            "location": "",
            "description": "",
            "submitter_name": "",
            "submitter_email": "",
        }
        response = self.post_event(payload)

        self.assertEqual(response.status_code, 201)
        event = Event.objects.get()
        self.assertIsNone(event.end_at)
        self.assertEqual(event.event_url, "")
        self.assertEqual(event.submitter_name, "")
        self.assertEqual(event.submitter_email, "")
        self.assertIsNone(response.json()["event"]["end_at"])

    def test_required_fields_return_field_specific_errors(self):
        response = self.post_event({
            "title": "",
            "date": "",
            "start_time": "",
            "time_zone": "",
            "categories": [],
        })

        self.assertEqual(response.status_code, 400)
        self.assertCountEqual(
            response.json()["errors"].keys(),
            ["title", "date", "start_time", "time_zone", "categories"],
        )
        self.assertEqual(Event.objects.count(), 0)

    def test_rejects_end_before_start(self):
        response = self.post_event(self.valid_payload(start_time="20:00", end_time="18:00"))

        self.assertEqual(response.status_code, 400)
        self.assertIn("end_time", response.json()["errors"])

    def test_rejects_unknown_category(self):
        response = self.post_event(self.valid_payload(categories=["Not a category"]))

        self.assertEqual(response.status_code, 400)
        self.assertIn("categories", response.json()["errors"])

    def test_rejects_invalid_timezone_url_and_email(self):
        response = self.post_event(self.valid_payload(
            time_zone="Mars/Olympus",
            event_url="javascript:alert(1)",
            location="www.example.com/meeting",
            submitter_email="not-an-email",
        ))

        self.assertEqual(response.status_code, 400)
        self.assertIn("time_zone", response.json()["errors"])
        self.assertIn("event_url", response.json()["errors"])
        self.assertIn("location", response.json()["errors"])
        self.assertIn("submitter_email", response.json()["errors"])

    def test_sanitizes_text_and_enforces_length_limits(self):
        response = self.post_event(self.valid_payload(
            title="<b>Community</b>   Workshop",
            description="<script>alert('x')</script> Useful details.",
        ))

        self.assertEqual(response.status_code, 201)
        event = Event.objects.get()
        self.assertEqual(event.title, "Community Workshop")
        self.assertNotIn("<script>", event.description)

        cache.clear()
        response = self.post_event(self.valid_payload(title="x" * 181))
        self.assertEqual(response.status_code, 400)
        self.assertIn("title", response.json()["errors"])

    def test_duplicate_submission_is_rejected_and_saved_once(self):
        first = self.post_event()
        second = self.post_event()

        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 409)
        self.assertIn(first.json()["event"]["reference"], second.json()["errors"]["form"])
        self.assertEqual(Event.objects.count(), 1)

    def test_basic_rate_limit_rejects_sixth_submission(self):
        for index in range(5):
            response = self.post_event(self.valid_payload(title=f"Event {index}"))
            self.assertEqual(response.status_code, 201)

        response = self.post_event(self.valid_payload(title="Event 6"))

        self.assertEqual(response.status_code, 429)
        self.assertIn("10 minutes", response.json()["errors"]["form"])
        self.assertEqual(Event.objects.count(), 5)

    def test_public_list_includes_pending_but_excludes_rejected_events(self):
        published = self.make_event(title="Published")
        cancelled = self.make_event(title="Cancelled", status=Event.Status.CANCELLED)
        pending = self.make_event(title="Pending", status=Event.Status.PENDING)
        self.make_event(title="Rejected", status=Event.Status.REJECTED)

        response = self.client.get("/api/events/")

        self.assertEqual(response.status_code, 200)
        public_events = response.json()["events"]
        self.assertCountEqual(
            [event["id"] for event in public_events],
            [published.id, cancelled.id, pending.id],
        )
        cancelled_payload = next(event for event in public_events if event["id"] == cancelled.id)
        self.assertEqual(cancelled_payload["status"], "cancelled")

    def test_month_window_returns_only_overlapping_public_events(self):
        november = self.make_event(title="November")
        self.make_event(
            title="December",
            start_at=timezone.make_aware(datetime(2026, 12, 2, 18, 0)),
        )

        response = self.client.get(
            "/api/events/?start=2026-11-01T00:00:00-05:00&end=2026-12-01T00:00:00-05:00"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual([event["id"] for event in response.json()["events"]], [november.id])

    def test_public_event_detail_hides_non_public_events(self):
        published = self.make_event(title="Published")
        rejected = self.make_event(title="Rejected", status=Event.Status.REJECTED)

        response = self.client.get(f"/api/events/{published.id}/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["event"]["id"], published.id)

        response = self.client.get(f"/api/events/{rejected.id}/")
        self.assertEqual(response.status_code, 404)


class VideoApiTests(TestCase):
    def valid_payload(self, **overrides):
        payload = {
            "youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "categories": ["Tech", "Education"],
            "submitter_name": "",
            "description": "",
        }
        payload.update(overrides)
        return payload

    def post_video(self, payload=None):
        return self.client.post(
            "/api/videos/",
            json.dumps(payload or self.valid_payload()),
            content_type="application/json",
        )

    def test_non_youtube_url_is_rejected(self):
        response = self.post_video(self.valid_payload(youtube_url="https://example.com/video"))

        self.assertEqual(response.status_code, 400)
        self.assertIn("youtube_url", response.json()["errors"])
        self.assertEqual(Video.objects.count(), 0)

    def test_structurally_invalid_youtube_url_is_rejected(self):
        response = self.post_video(self.valid_payload(youtube_url="https://youtube.com/watch?v=short"))

        self.assertEqual(response.status_code, 400)
        self.assertIn("youtube_url", response.json()["errors"])

    def test_submission_requires_at_least_one_category(self):
        response = self.post_video(self.valid_payload(categories=[]))

        self.assertEqual(response.status_code, 400)
        self.assertIn("categories", response.json()["errors"])

    def test_multiple_categories_and_blank_optional_fields_are_accepted(self):
        response = self.post_video()

        self.assertEqual(response.status_code, 201)
        video = Video.objects.get()
        self.assertEqual(video.categories, ["Tech", "Education"])
        self.assertEqual(video.submitter_name, "")
        self.assertEqual(video.description, "")
        self.assertEqual(video.status, Video.Status.PENDING)
        self.assertEqual(response.json()["video"]["reference"], f"SSP-VID-{video.id:06d}")

    def test_pending_and_rejected_videos_are_not_public(self):
        Video.objects.create(
            youtube_url="https://youtu.be/dQw4w9WgXcQ",
            youtube_id="dQw4w9WgXcQ",
            categories=["Community"],
        )
        Video.objects.create(
            youtube_url="https://youtu.be/9bZkp7q19f0",
            youtube_id="9bZkp7q19f0",
            categories=["Others"],
            status=Video.Status.REJECTED,
        )

        response = self.client.get("/api/videos/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["videos"], [])

    def test_approved_video_appears_publicly_without_authentication(self):
        video = Video.objects.create(
            youtube_url="https://youtu.be/dQw4w9WgXcQ",
            youtube_id="dQw4w9WgXcQ",
            categories=["Community", "Arts & Culture"],
            status=Video.Status.PUBLISHED,
        )

        response = self.client.get("/api/videos/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual([item["id"] for item in response.json()["videos"]], [video.id])
