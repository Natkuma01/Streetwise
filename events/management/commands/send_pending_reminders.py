"""Remind the admin about events that have waited too long for review.

Run it every hour from cron (see docs/deploy-aws.md). It is safe to run as
often as you like: each event is reminded about once, then marked. An event
that is edited again goes back to "not reminded", so it can be reminded again.
"""

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from events.emails import send_pending_reminder_email
from events.models import Event


class Command(BaseCommand):
    help = "Email the admin once about pending events older than --hours (default 24)."

    def add_arguments(self, parser):
        parser.add_argument("--hours", type=int, default=24, help="How long an event may wait.")
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be sent. Sends nothing and marks nothing.",
        )

    def handle(self, *args, **options):
        hours = options["hours"]
        cutoff = timezone.now() - timedelta(hours=hours)

        # updated_at, not created_at: a fresh edit restarts the wait.
        waiting = list(
            Event.objects.filter(
                status=Event.Status.PENDING,
                reminder_sent_at__isnull=True,
                updated_at__lte=cutoff,
            ).order_by("start_at")
        )

        if not waiting:
            self.stdout.write("No events are waiting for a reminder.")
            return

        if options["dry_run"]:
            self.stdout.write(f"Would remind about {len(waiting)} event(s):")
            for event in waiting:
                self.stdout.write(f"  {event.ref_number}  {event.title}")
            return

        if not send_pending_reminder_email(waiting, hours):
            # Leave them unmarked so the next run tries again.
            self.stderr.write("The reminder email could not be sent. Will retry on the next run.")
            return

        # update_fields keeps updated_at as it was. Otherwise sending the
        # reminder would look like an edit and restart the clock.
        now = timezone.now()
        for event in waiting:
            event.reminder_sent_at = now
            event.save(update_fields=["reminder_sent_at"])
        self.stdout.write(f"Reminded the admin about {len(waiting)} event(s).")
