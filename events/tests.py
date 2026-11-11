import json

from django.test import TestCase

from .models import Event


class EventApiTests(TestCase):
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
