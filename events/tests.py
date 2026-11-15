import json
from datetime import datetime, timedelta

from django.test import TestCase
from django.utils import timezone

from .models import Event


class EventApiTests(TestCase):
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

    def test_create_and_list_event(self):
        payload = {
            "title": "A useful NYC talk",
            "start_at": "2026-11-18T18:00:00",
            "end_at": "2026-11-18T19:30:00",
            "event_url": "https://example.com/event",
            "categories": ["Tech", "Education"],
            "location": "Online",
            "description": "An open community lecture.",
        }
        response = self.client.post("/api/events/", json.dumps(payload), content_type="application/json")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(Event.objects.count(), 1)
        self.assertEqual(response.json()["event"]["status"], "pending")

        response = self.client.get("/api/events/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["events"][0]["title"], payload["title"])

    def test_rejects_end_before_start(self):
        payload = {
            "title": "Invalid event",
            "start_at": "2026-11-18T20:00:00",
            "end_at": "2026-11-18T18:00:00",
            "event_url": "https://example.com/event",
            "categories": ["Others"],
        }
        response = self.client.post("/api/events/", json.dumps(payload), content_type="application/json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("end_at", response.json()["errors"])

    def test_rejects_unknown_category(self):
        payload = {
            "title": "Invalid event",
            "start_at": "2026-11-18T18:00:00",
            "end_at": "2026-11-18T19:00:00",
            "event_url": "https://example.com/event",
            "categories": ["Not a category"],
        }
        response = self.client.post("/api/events/", json.dumps(payload), content_type="application/json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("categories", response.json()["errors"])

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
