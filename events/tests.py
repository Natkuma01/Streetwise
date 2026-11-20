from datetime import timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.core import mail
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import Category, Event


def make_event(**overrides):
    fields = {
        "title": "Intro to threat modeling",
        "submitter_email": "sam@example.com",
        "start_at": timezone.now() + timedelta(days=7),
        "event_link": "https://example.com/threat-modeling",
        "attendance_mode": Event.AttendanceMode.VIRTUAL,
    }
    fields.update(overrides)
    event = Event.objects.create(**fields)
    event.categories.add(Category.objects.get(name="Cybersecurity"))
    return event


def valid_payload(**overrides):
    payload = {
        "title": "Resume workshop",
        "submitter_email": "pat@example.com",
        "start_at": (timezone.now() + timedelta(days=3)).isoformat(),
        "event_link": "https://example.com/resume",
        "attendance_mode": "in_person",
        "categories": [Category.objects.get(name="Human Resources").pk],
    }
    payload.update(overrides)
    return payload


@override_settings(
    ADMIN_NOTIFICATION_EMAIL="inbox@streetwise.test",
    DEFAULT_FROM_EMAIL="inbox@streetwise.test",
    FRONTEND_BASE_URL="https://streetwise.test",
)
class ModelTests(TestCase):
    def test_starting_categories_are_loaded(self):
        names = set(Category.objects.values_list("name", flat=True))
        self.assertEqual(
            names,
            {
                "Cybersecurity",
                "Finance",
                "Human Resources",
                "Web Developer",
                "Business",
                "Marketing",
                "Data Analyst/Engineer",
                "Others",
            },
        )

    def test_new_event_defaults(self):
        event = make_event()
        self.assertEqual(event.status, Event.Status.PENDING)
        self.assertRegex(event.reference_number, r"^SW-[0-9A-F]{8}$")
        self.assertIsNotNone(event.manage_key)
        self.assertIsNone(event.reminder_sent_at)

    def test_reference_number_and_manage_key_are_unique_per_event(self):
        a, b = make_event(), make_event()
        self.assertNotEqual(a.reference_number, b.reference_number)
        self.assertNotEqual(a.manage_key, b.manage_key)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Event.objects.create(
                title="Copy",
                submitter_email="x@example.com",
                start_at=timezone.now() + timedelta(days=1),
                event_link="https://example.com",
                attendance_mode="virtual",
                reference_number=a.reference_number,
            )

    def test_event_can_have_many_categories(self):
        event = make_event()
        event.categories.add(*Category.objects.filter(name__in=["Finance", "Marketing"]))
        self.assertEqual(event.categories.count(), 3)


@override_settings(
    ADMIN_NOTIFICATION_EMAIL="inbox@streetwise.test",
    DEFAULT_FROM_EMAIL="inbox@streetwise.test",
    FRONTEND_BASE_URL="https://streetwise.test",
)
class ApiTests(TestCase):
    events_url = reverse("event-list-create")

    def test_list_shows_pending_and_approved_with_status(self):
        pending = make_event(title="Pending one")
        approved = make_event(title="Approved one", status=Event.Status.APPROVED)
        response = self.client.get(self.events_url)
        self.assertEqual(response.status_code, 200)
        by_title = {e["title"]: e["status"] for e in response.json()}
        self.assertEqual(by_title, {"Pending one": "pending", "Approved one": "approved"})
        self.assertIsNotNone(pending.pk and approved.pk)

    def test_list_hides_rejected_and_cancelled(self):
        make_event(title="Rejected", status=Event.Status.REJECTED)
        make_event(title="Cancelled", status=Event.Status.CANCELLED)
        self.assertEqual(self.client.get(self.events_url).json(), [])

    def test_list_never_exposes_secrets(self):
        event = make_event(submitter_name="")
        body = self.client.get(self.events_url).content.decode()
        self.assertNotIn(str(event.manage_key), body)
        self.assertNotIn(event.reference_number, body)
        self.assertNotIn("sam@example.com", body)
        self.assertNotIn("manage_key", body)
        self.assertEqual(self.client.get(self.events_url).json()[0]["submitter_name"], "Anonymous")

    def test_list_filters_by_date_range(self):
        soon = make_event(title="Soon", start_at=timezone.now() + timedelta(days=2))
        later = make_event(title="Later", start_at=timezone.now() + timedelta(days=40))
        window_end = (timezone.now() + timedelta(days=10)).date().isoformat()
        titles = [e["title"] for e in self.client.get(self.events_url, {"end": window_end}).json()]
        self.assertEqual(titles, ["Soon"])
        window_start = (timezone.now() + timedelta(days=20)).date().isoformat()
        titles = [e["title"] for e in self.client.get(self.events_url, {"start": window_start}).json()]
        self.assertEqual(titles, ["Later"])
        self.assertIsNotNone(soon.pk and later.pk)

    def test_list_rejects_a_bad_range_value(self):
        response = self.client.get(self.events_url, {"start": "next tuesday"})
        self.assertEqual(response.status_code, 400)
        self.assertIn("start", response.json())

    def test_times_are_returned_in_utc(self):
        make_event(start_at=timezone.now() + timedelta(days=2))
        body = self.client.get(self.events_url).json()[0]
        self.assertTrue(body["start_at"].endswith("Z"), body["start_at"])

    def test_categories_endpoint(self):
        response = self.client.get(reverse("category-list"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 8)
        self.assertEqual(set(response.json()[0]), {"id", "name"})

    def test_create_saves_a_pending_event_with_reference_number(self):
        response = self.client.post(self.events_url, valid_payload(), content_type="application/json")
        self.assertEqual(response.status_code, 201, response.content)
        body = response.json()
        self.assertEqual(body["status"], "pending")
        self.assertRegex(body["reference_number"], r"^SW-[0-9A-F]{8}$")
        event = Event.objects.get(reference_number=body["reference_number"])
        self.assertEqual(event.status, Event.Status.PENDING)
        self.assertEqual(event.categories.count(), 1)

    def test_create_ignores_a_status_sent_by_the_client(self):
        payload = valid_payload(status="approved")
        response = self.client.post(self.events_url, payload, content_type="application/json")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["status"], "pending")

    def test_create_response_never_returns_the_manage_key(self):
        response = self.client.post(self.events_url, valid_payload(), content_type="application/json")
        event = Event.objects.get()
        self.assertNotIn(str(event.manage_key), response.content.decode())
        self.assertNotIn("manage_key", response.content.decode())

    def test_create_needs_no_login_or_csrf_token(self):
        from django.test import Client

        strict = Client(enforce_csrf_checks=True)
        response = strict.post(self.events_url, valid_payload(), content_type="application/json")
        self.assertEqual(response.status_code, 201)

    def test_create_requires_every_required_field(self):
        response = self.client.post(self.events_url, {}, content_type="application/json")
        self.assertEqual(response.status_code, 400)
        missing = set(response.json())
        self.assertEqual(
            missing,
            {"title", "submitter_email", "start_at", "event_link", "attendance_mode", "categories"},
        )
        self.assertEqual(Event.objects.count(), 0)

    def test_create_rejects_a_past_start(self):
        past = (timezone.now() - timedelta(hours=1)).isoformat()
        response = self.client.post(
            self.events_url, valid_payload(start_at=past), content_type="application/json"
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("start_at", response.json())
        self.assertEqual(Event.objects.count(), 0)

    def test_create_rejects_empty_categories(self):
        response = self.client.post(
            self.events_url, valid_payload(categories=[]), content_type="application/json"
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["categories"], ["Choose at least one category."])

    def test_create_rejects_an_unknown_category(self):
        response = self.client.post(
            self.events_url, valid_payload(categories=[99999]), content_type="application/json"
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("categories", response.json())

    def test_create_rejects_end_before_start(self):
        payload = valid_payload(end_at=(timezone.now() + timedelta(days=2)).isoformat())
        response = self.client.post(self.events_url, payload, content_type="application/json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("end_at", response.json())

    def test_create_rejects_bad_email_and_unsafe_links(self):
        for field, value in [
            ("submitter_email", "not-an-email"),
            ("event_link", "javascript:alert(1)"),
            ("event_link", "ftp://example.com/file"),
            ("event_link", "not a url"),
        ]:
            with self.subTest(field=field, value=value):
                response = self.client.post(
                    self.events_url, valid_payload(**{field: value}), content_type="application/json"
                )
                self.assertEqual(response.status_code, 400)
                self.assertIn(field, response.json())

    def test_create_rejects_a_bad_attendance_mode(self):
        response = self.client.post(
            self.events_url, valid_payload(attendance_mode="hybrid"), content_type="application/json"
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("attendance_mode", response.json())

    def test_create_sends_receipt_and_admin_emails(self):
        self.client.post(self.events_url, valid_payload(), content_type="application/json")
        event = Event.objects.get()
        self.assertEqual(len(mail.outbox), 2)
        receipt = next(m for m in mail.outbox if m.to == ["pat@example.com"])
        admin_note = next(m for m in mail.outbox if m.to == ["inbox@streetwise.test"])
        self.assertIn(event.reference_number, receipt.body)
        self.assertIn(f"https://streetwise.test/events/manage/{event.manage_key}", receipt.body)
        self.assertIn(event.reference_number, admin_note.body)
        self.assertNotIn(str(event.manage_key), admin_note.body)

    def test_event_still_saves_when_email_fails(self):
        with mock.patch("events.emails.send_mail", side_effect=OSError("smtp is down")):
            with self.assertLogs("events.emails", level="ERROR"):
                response = self.client.post(
                    self.events_url, valid_payload(), content_type="application/json"
                )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(Event.objects.count(), 1)

    def test_get_only_methods_are_not_writable(self):
        self.assertEqual(self.client.delete(self.events_url).status_code, 405)
        self.assertEqual(self.client.post(reverse("category-list"), {}).status_code, 405)


@override_settings(DEFAULT_FROM_EMAIL="inbox@streetwise.test")
class AdminTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin_user = get_user_model().objects.create_superuser(
            "admin", "admin@example.com", "pw-for-tests-only"
        )

    def setUp(self):
        self.client.force_login(self.admin_user)
        self.changelist = reverse("admin:events_event_changelist")

    def test_pending_events_are_listed_first(self):
        approved = make_event(title="Approved early", status=Event.Status.APPROVED,
                              start_at=timezone.now() + timedelta(days=1))
        pending = make_event(title="Pending later", start_at=timezone.now() + timedelta(days=30))
        response = self.client.get(self.changelist)
        self.assertEqual(response.status_code, 200)
        rows = [e.pk for e in response.context["cl"].result_list]
        self.assertEqual(rows, [pending.pk, approved.pk])

    def test_can_filter_by_status(self):
        make_event(title="Mine pending")
        make_event(title="Mine approved", status=Event.Status.APPROVED)
        response = self.client.get(self.changelist, {"status__exact": "pending"})
        titles = [e.title for e in response.context["cl"].result_list]
        self.assertEqual(titles, ["Mine pending"])

    def test_approve_action_publishes_and_emails_the_submitter(self):
        event = make_event()
        response = self.client.post(
            self.changelist,
            {"action": "approve_events", "_selected_action": [event.pk]},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        event.refresh_from_db()
        self.assertEqual(event.status, Event.Status.APPROVED)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["sam@example.com"])
        self.assertIn(event.reference_number, mail.outbox[0].body)

    def test_reject_action_hides_the_event_and_sends_no_email(self):
        event = make_event()
        self.client.post(
            self.changelist,
            {"action": "reject_events", "_selected_action": [event.pk]},
            follow=True,
        )
        event.refresh_from_db()
        self.assertEqual(event.status, Event.Status.REJECTED)
        self.assertEqual(len(mail.outbox), 0)
        self.assertTrue(Event.objects.filter(pk=event.pk).exists())
        public = self.client.get(reverse("event-list-create")).json()
        self.assertEqual(public, [])

    def test_cancel_action_sends_no_email(self):
        event = make_event()
        self.client.post(
            self.changelist,
            {"action": "cancel_events", "_selected_action": [event.pk]},
            follow=True,
        )
        event.refresh_from_db()
        self.assertEqual(event.status, Event.Status.CANCELLED)
        self.assertEqual(len(mail.outbox), 0)

    def test_approving_twice_does_not_email_twice(self):
        event = make_event(status=Event.Status.APPROVED)
        self.client.post(
            self.changelist,
            {"action": "approve_events", "_selected_action": [event.pk]},
            follow=True,
        )
        self.assertEqual(len(mail.outbox), 0)

    def test_changing_status_in_the_edit_form_emails_the_submitter(self):
        event = make_event()
        url = reverse("admin:events_event_change", args=[event.pk])
        form = {
            "title": event.title,
            "submitter_email": event.submitter_email,
            "submitter_name": "",
            "start_at_0": event.start_at.strftime("%Y-%m-%d"),
            "start_at_1": event.start_at.strftime("%H:%M:%S"),
            "event_link": event.event_link,
            "attendance_mode": event.attendance_mode,
            "description": "",
            "categories": [c.pk for c in event.categories.all()],
            "status": "approved",
        }
        response = self.client.post(url, form, follow=True)
        self.assertEqual(response.status_code, 200)
        event.refresh_from_db()
        self.assertEqual(event.status, Event.Status.APPROVED)
        self.assertEqual(len(mail.outbox), 1)

    def test_admin_can_delete_an_event(self):
        event = make_event()
        self.client.post(
            self.changelist,
            {"action": "delete_selected", "_selected_action": [event.pk], "post": "yes"},
            follow=True,
        )
        self.assertFalse(Event.objects.filter(pk=event.pk).exists())

    def test_manage_key_is_not_shown_in_admin(self):
        event = make_event()
        response = self.client.get(reverse("admin:events_event_change", args=[event.pk]))
        self.assertNotContains(response, str(event.manage_key))

    def test_anonymous_visitors_cannot_reach_admin(self):
        self.client.logout()
        response = self.client.get(self.changelist)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/admin/login/", response["Location"])
