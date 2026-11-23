from datetime import timedelta
from io import StringIO
from unittest import mock

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import Category, Event


# Settings every API test class shares. Tests use an in-memory cache so they
# never touch the real file cache, and the limits are high enough that normal
# tests are never throttled. Throttle tests lower the rate on purpose.
API_SETTINGS = dict(
    ADMIN_NOTIFICATION_EMAIL="inbox@streetwise.test",
    DEFAULT_FROM_EMAIL="inbox@streetwise.test",
    FRONTEND_BASE_URL="https://streetwise.test",
    CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}},
    EVENT_SUBMIT_RATE="1000/hour",
    MANAGE_RATE="1000/hour",
)


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
        self.assertRegex(event.ref_number, r"^SW-[0-9A-F]{8}$")
        self.assertIsNotNone(event.manage_key)
        self.assertIsNone(event.reminder_sent_at)

    def test_reference_number_and_manage_key_are_unique_per_event(self):
        a, b = make_event(), make_event()
        self.assertNotEqual(a.ref_number, b.ref_number)
        self.assertNotEqual(a.manage_key, b.manage_key)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Event.objects.create(
                title="Copy",
                submitter_email="x@example.com",
                start_at=timezone.now() + timedelta(days=1),
                event_link="https://example.com",
                attendance_mode="virtual",
                ref_number=a.ref_number,
            )

    def test_event_can_have_many_categories(self):
        event = make_event()
        event.categories.add(*Category.objects.filter(name__in=["Finance", "Marketing"]))
        self.assertEqual(event.categories.count(), 3)


@override_settings(**API_SETTINGS)
class ApiTests(TestCase):
    events_url = reverse("event-list-create")

    def setUp(self):
        cache.clear()

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
        self.assertNotIn(event.ref_number, body)
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
        self.assertRegex(body["ref_number"], r"^SW-[0-9A-F]{8}$")
        event = Event.objects.get(ref_number=body["ref_number"])
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
        self.assertIn(event.ref_number, receipt.body)
        self.assertIn(f"https://streetwise.test/events/manage#{event.manage_key}", receipt.body)
        self.assertIn(event.ref_number, admin_note.body)
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


@override_settings(**API_SETTINGS)
class SpamProtectionTests(TestCase):
    events_url = reverse("event-list-create")

    def setUp(self):
        cache.clear()

    def post(self, **overrides):
        return self.client.post(self.events_url, valid_payload(**overrides), content_type="application/json")

    def test_empty_honeypot_is_a_normal_submit(self):
        response = self.post(fax_number="")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(Event.objects.count(), 1)

    def test_filled_honeypot_looks_like_success_but_saves_nothing(self):
        response = self.post(fax_number="555-0100")
        self.assertEqual(response.status_code, 201)
        self.assertRegex(response.json()["ref_number"], r"^SW-[0-9A-F]{8}$")
        self.assertEqual(Event.objects.count(), 0)
        self.assertEqual(len(mail.outbox), 0)

    def test_honeypot_catches_a_bot_even_when_the_rest_is_invalid(self):
        response = self.client.post(
            self.events_url, {"fax_number": "x"}, content_type="application/json"
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(Event.objects.count(), 0)

    def test_a_json_list_body_does_not_crash_the_honeypot_check(self):
        response = self.client.post(self.events_url, [1, 2], content_type="application/json")
        self.assertEqual(response.status_code, 400)

    @override_settings(EVENT_SUBMIT_RATE="3/hour")
    def test_fourth_submit_in_an_hour_is_blocked(self):
        for _ in range(3):
            self.assertEqual(self.post().status_code, 201)
        response = self.post()
        self.assertEqual(response.status_code, 429)
        self.assertIn("Retry-After", response)
        self.assertEqual(Event.objects.count(), 3)

    @override_settings(EVENT_SUBMIT_RATE="3/hour")
    def test_bot_posts_count_toward_the_limit(self):
        for _ in range(3):
            self.post(fax_number="spam")
        self.assertEqual(self.post().status_code, 429)

    @override_settings(EVENT_SUBMIT_RATE="1/hour")
    def test_reading_the_calendar_is_never_limited(self):
        self.post()
        for _ in range(5):
            self.assertEqual(self.client.get(self.events_url).status_code, 200)

    @override_settings(EVENT_SUBMIT_RATE="1/hour")
    def test_limit_is_per_ip_address(self):
        first = self.client.post(
            self.events_url, valid_payload(), content_type="application/json", REMOTE_ADDR="1.1.1.1"
        )
        again = self.client.post(
            self.events_url, valid_payload(), content_type="application/json", REMOTE_ADDR="1.1.1.1"
        )
        other = self.client.post(
            self.events_url, valid_payload(), content_type="application/json", REMOTE_ADDR="2.2.2.2"
        )
        self.assertEqual((first.status_code, again.status_code, other.status_code), (201, 429, 201))


@override_settings(**API_SETTINGS)
class ManageLinkTests(TestCase):
    url = reverse("manage-event")
    cancel_url = reverse("manage-cancel")

    def setUp(self):
        cache.clear()
        self.event = make_event()
        self.key = str(self.event.manage_key)

    def get(self, key=None):
        return self.client.get(self.url, headers={"X-Manage-Key": key or self.key})

    def patch(self, data, key=None):
        return self.client.patch(
            self.url, data, content_type="application/json", headers={"X-Manage-Key": key or self.key}
        )

    def cancel(self, key=None):
        return self.client.post(self.cancel_url, headers={"X-Manage-Key": key or self.key})

    # --- finding the event ---

    def test_get_returns_the_owners_event(self):
        response = self.get()
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["ref_number"], self.event.ref_number)
        self.assertEqual(body["submitter_email"], "sam@example.com")
        self.assertNotIn("manage_key", body)
        self.assertNotIn(self.key, response.content.decode())

    def test_responses_are_never_cached(self):
        self.assertIn("no-store", self.get()["Cache-Control"])
        self.assertIn("no-store", self.get(key="nonsense")["Cache-Control"])

    def test_missing_unknown_and_malformed_keys_are_all_404(self):
        self.assertEqual(self.client.get(self.url).status_code, 404)
        self.assertEqual(self.get(key="not-a-uuid").status_code, 404)
        self.assertEqual(self.get(key="00000000-0000-4000-8000-000000000000").status_code, 404)

    def test_key_in_the_url_or_query_string_is_ignored(self):
        self.assertEqual(self.client.get(self.url, {"key": self.key}).status_code, 404)

    def test_link_expires_a_few_days_after_the_event_ends(self):
        Event.objects.filter(pk=self.event.pk).update(
            start_at=timezone.now() - timedelta(days=10), end_at=None
        )
        self.assertEqual(self.get().status_code, 410)
        self.assertEqual(self.patch({"title": "x"}).status_code, 410)
        self.assertEqual(self.cancel().status_code, 410)

    def test_link_still_works_inside_the_grace_period(self):
        Event.objects.filter(pk=self.event.pk).update(
            start_at=timezone.now() - timedelta(days=2), end_at=None
        )
        self.assertEqual(self.get().status_code, 200)

    def test_grace_period_counts_from_the_end_time_when_there_is_one(self):
        Event.objects.filter(pk=self.event.pk).update(
            start_at=timezone.now() - timedelta(days=10),
            end_at=timezone.now() - timedelta(days=1),
        )
        self.assertEqual(self.get().status_code, 200)

    # --- editing ---

    def test_editing_a_pending_event_keeps_it_pending_and_sends_no_admin_email(self):
        mail.outbox.clear()
        response = self.patch({"title": "New title", "description": "More detail"})
        self.assertEqual(response.status_code, 200)
        self.event.refresh_from_db()
        self.assertEqual((self.event.title, self.event.description), ("New title", "More detail"))
        self.assertEqual(self.event.status, Event.Status.PENDING)
        self.assertEqual(len(mail.outbox), 0)

    def test_editing_an_approved_event_sends_it_back_to_pending_and_tells_the_admin(self):
        Event.objects.filter(pk=self.event.pk).update(status=Event.Status.APPROVED)
        mail.outbox.clear()
        response = self.patch({"title": "Changed"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "pending")
        self.event.refresh_from_db()
        self.assertEqual(self.event.status, Event.Status.PENDING)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["inbox@streetwise.test"])
        self.assertIn("Edited event needs review", mail.outbox[0].subject)
        self.assertNotIn(self.key, mail.outbox[0].body)

    def test_saving_without_changes_keeps_an_approved_event_approved(self):
        Event.objects.filter(pk=self.event.pk).update(status=Event.Status.APPROVED)
        mail.outbox.clear()
        response = self.patch({"title": self.event.title, "categories": [c.pk for c in self.event.categories.all()]})
        self.assertEqual(response.status_code, 200)
        self.event.refresh_from_db()
        self.assertEqual(self.event.status, Event.Status.APPROVED)
        self.assertEqual(len(mail.outbox), 0)
        self.assertEqual(self.patch({}).status_code, 200)

    def test_changing_categories_counts_as_a_change(self):
        Event.objects.filter(pk=self.event.pk).update(status=Event.Status.APPROVED)
        finance = Category.objects.get(name="Finance")
        response = self.patch({"categories": [finance.pk]})
        self.assertEqual(response.status_code, 200)
        self.assertEqual([c["name"] for c in response.json()["categories"]], ["Finance"])
        self.event.refresh_from_db()
        self.assertEqual(self.event.status, Event.Status.PENDING)

    def test_an_edit_starts_the_reminder_clock_over(self):
        Event.objects.filter(pk=self.event.pk).update(reminder_sent_at=timezone.now())
        self.patch({"title": "Again"})
        self.event.refresh_from_db()
        self.assertIsNone(self.event.reminder_sent_at)

    def test_owner_cannot_change_email_status_or_reference(self):
        response = self.patch(
            {
                "title": "Fine",
                "submitter_email": "thief@example.com",
                "status": "approved",
                "ref_number": "SW-00000000",
                "manage_key": "00000000-0000-4000-8000-000000000000",
            }
        )
        self.assertEqual(response.status_code, 200)
        self.event.refresh_from_db()
        self.assertEqual(self.event.submitter_email, "sam@example.com")
        self.assertEqual(self.event.status, Event.Status.PENDING)
        self.assertNotEqual(self.event.ref_number, "SW-00000000")
        self.assertEqual(str(self.event.manage_key), self.key)

    def test_edit_is_validated_like_a_new_submit(self):
        self.assertEqual(self.patch({"title": ""}).status_code, 400)
        self.assertEqual(self.patch({"event_link": "ftp://example.com/x"}).status_code, 400)
        self.assertEqual(self.patch({"categories": []}).status_code, 400)
        past = (timezone.now() - timedelta(days=1)).isoformat()
        self.assertEqual(self.patch({"start_at": past}).status_code, 400)

    def test_end_must_be_after_start_using_saved_values_too(self):
        # Only the end is sent. It is compared with the saved start.
        early_end = (self.event.start_at - timedelta(hours=1)).isoformat()
        self.assertEqual(self.patch({"end_at": early_end}).status_code, 400)
        # Only the start is sent. It is compared with the saved end.
        Event.objects.filter(pk=self.event.pk).update(end_at=self.event.start_at + timedelta(hours=2))
        late_start = (self.event.start_at + timedelta(hours=5)).isoformat()
        self.assertEqual(self.patch({"start_at": late_start}).status_code, 400)

    def test_unchanged_past_start_does_not_block_other_edits(self):
        past = timezone.now() - timedelta(hours=1)
        Event.objects.filter(pk=self.event.pk).update(start_at=past)
        response = self.patch({"start_at": past.isoformat(), "description": "Still going"})
        self.assertEqual(response.status_code, 200)

    def test_end_time_can_be_cleared(self):
        Event.objects.filter(pk=self.event.pk).update(end_at=self.event.start_at + timedelta(hours=2))
        response = self.patch({"end_at": None})
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.json()["end_at"])

    def test_rejected_and_cancelled_events_cannot_be_edited(self):
        for state in (Event.Status.REJECTED, Event.Status.CANCELLED):
            Event.objects.filter(pk=self.event.pk).update(status=state)
            self.assertEqual(self.patch({"title": "x"}).status_code, 409)
            self.event.refresh_from_db()
            self.assertEqual(self.event.status, state)
            self.assertEqual(self.get().status_code, 200)

    # --- cancelling ---

    def test_cancel_hides_the_event_from_the_calendar(self):
        response = self.cancel()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "cancelled")
        self.event.refresh_from_db()
        self.assertEqual(self.event.status, Event.Status.CANCELLED)
        self.assertEqual(self.client.get(reverse("event-list-create")).json(), [])

    def test_cancel_works_on_an_approved_event(self):
        Event.objects.filter(pk=self.event.pk).update(status=Event.Status.APPROVED)
        self.assertEqual(self.cancel().status_code, 200)

    def test_cancelling_twice_is_fine(self):
        self.cancel()
        self.assertEqual(self.cancel().status_code, 200)

    def test_rejected_event_cannot_be_cancelled(self):
        Event.objects.filter(pk=self.event.pk).update(status=Event.Status.REJECTED)
        self.assertEqual(self.cancel().status_code, 409)

    def test_cancel_needs_a_valid_key(self):
        self.assertEqual(self.client.post(self.cancel_url).status_code, 404)
        self.event.refresh_from_db()
        self.assertEqual(self.event.status, Event.Status.PENDING)

    # --- rate limit ---

    @override_settings(MANAGE_RATE="3/hour")
    def test_guessing_keys_is_rate_limited(self):
        for _ in range(3):
            self.assertEqual(self.get(key="00000000-0000-4000-8000-000000000000").status_code, 404)
        self.assertEqual(self.get().status_code, 429)

    def test_edit_and_cancel_do_not_leak_other_events(self):
        other = make_event(title="Someone else")
        self.patch({"title": "Mine"})
        other.refresh_from_db()
        self.assertEqual(other.title, "Someone else")


@override_settings(DEFAULT_FROM_EMAIL="inbox@streetwise.test", ADMIN_NOTIFICATION_EMAIL="inbox@streetwise.test")
class ReminderCommandTests(TestCase):
    def age(self, event, hours):
        # updated_at is auto_now, so move it with a queryset update.
        Event.objects.filter(pk=event.pk).update(updated_at=timezone.now() - timedelta(hours=hours))
        event.refresh_from_db()

    def run_command(self, *args):
        out, err = StringIO(), StringIO()
        call_command("send_pending_reminders", *args, stdout=out, stderr=err)
        return out.getvalue(), err.getvalue()

    def test_old_pending_events_get_one_email_listing_all_of_them(self):
        a, b = make_event(title="Old A"), make_event(title="Old B")
        self.age(a, 30)
        self.age(b, 25)
        make_event(title="Fresh")
        mail.outbox.clear()
        self.run_command()
        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertEqual(message.to, ["inbox@streetwise.test"])
        self.assertIn("2 events", message.subject)
        self.assertIn("Old A", message.body)
        self.assertIn("Old B", message.body)
        self.assertNotIn("Fresh", message.body)
        self.assertNotIn(str(a.manage_key), message.body)

    def test_each_event_is_reminded_only_once(self):
        event = make_event()
        self.age(event, 30)
        mail.outbox.clear()
        self.run_command()
        self.run_command()
        self.assertEqual(len(mail.outbox), 1)
        event.refresh_from_db()
        self.assertIsNotNone(event.reminder_sent_at)

    def test_marking_does_not_restart_the_clock(self):
        event = make_event()
        self.age(event, 30)
        before = event.updated_at
        self.run_command()
        event.refresh_from_db()
        self.assertEqual(event.updated_at, before)

    def test_approved_rejected_and_cancelled_events_are_ignored(self):
        for state in (Event.Status.APPROVED, Event.Status.REJECTED, Event.Status.CANCELLED):
            self.age(make_event(status=state), 100)
        mail.outbox.clear()
        out, _ = self.run_command()
        self.assertEqual(len(mail.outbox), 0)
        self.assertIn("No events", out)

    def test_nothing_is_sent_when_nothing_is_waiting(self):
        make_event()
        mail.outbox.clear()
        self.run_command()
        self.assertEqual(len(mail.outbox), 0)

    def test_hours_option_changes_the_wait(self):
        event = make_event()
        self.age(event, 3)
        mail.outbox.clear()
        self.run_command()
        self.assertEqual(len(mail.outbox), 0)
        self.run_command("--hours", "2")
        self.assertEqual(len(mail.outbox), 1)

    def test_dry_run_sends_and_marks_nothing(self):
        event = make_event()
        self.age(event, 30)
        mail.outbox.clear()
        out, _ = self.run_command("--dry-run")
        self.assertIn(event.ref_number, out)
        self.assertEqual(len(mail.outbox), 0)
        event.refresh_from_db()
        self.assertIsNone(event.reminder_sent_at)

    def test_a_failed_send_is_retried_on_the_next_run(self):
        event = make_event()
        self.age(event, 30)
        with mock.patch("events.emails.send_mail", side_effect=OSError("smtp down")):
            _, err = self.run_command()
        self.assertIn("could not be sent", err)
        event.refresh_from_db()
        self.assertIsNone(event.reminder_sent_at)
        mail.outbox.clear()
        self.run_command()
        self.assertEqual(len(mail.outbox), 1)

    def test_an_edited_event_can_be_reminded_again(self):
        event = make_event()
        self.age(event, 30)
        self.run_command()
        event.refresh_from_db()
        # Simulate what the manage link does on an edit.
        event.reminder_sent_at = None
        event.save()
        self.age(event, 30)
        mail.outbox.clear()
        self.run_command()
        self.assertEqual(len(mail.outbox), 1)


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
        self.assertIn(event.ref_number, mail.outbox[0].body)

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
