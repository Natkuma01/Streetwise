"""Emails the site sends.

Every function here swallows send errors and logs them. A broken mail server
must never stop an event from being saved or approved. The cost is that a
failed email is only visible in the server log, so check it during testing.
"""

import logging

from django.conf import settings
from django.core.mail import send_mail

logger = logging.getLogger(__name__)


def manage_link(event):
    return f"{settings.FRONTEND_BASE_URL}/events/manage/{event.manage_key}"


def _send(subject, message, recipient):
    if not recipient:
        logger.warning("Email %r skipped: no recipient configured.", subject)
        return False
    try:
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [recipient],
            fail_silently=False,
        )
    except Exception:
        logger.exception("Could not send email %r to %s", subject, recipient)
        return False
    return True


def send_receipt_email(event):
    """To the submitter, right after they submit."""
    message = (
        f"Thank you for sharing \"{event.title}\" with Streetwise.\n\n"
        "Your event is waiting for review. We aim to approve it within 24 hours.\n"
        "Until then it shows on the calendar in a faded style.\n\n"
        f"Reference number: {event.reference_number}\n\n"
        "Need to fix a detail or cancel? Use your private link:\n"
        f"{manage_link(event)}\n\n"
        "Keep this email. Anyone with that link can change your event, "
        "so please do not forward it."
    )
    return _send(
        f"We got your event: {event.title} ({event.reference_number})",
        message,
        event.submitter_email,
    )


def send_admin_new_event_email(event):
    """To the project inbox, so someone knows an event is waiting."""
    message = (
        "A new event is waiting for review.\n\n"
        f"Title: {event.title}\n"
        f"Reference number: {event.reference_number}\n"
        f"Starts: {event.start_at:%Y-%m-%d %H:%M} UTC\n"
        f"Submitted by: {event.submitter_email}\n\n"
        "Review it in Django admin: set its status to Approved or Rejected."
    )
    return _send(
        f"New event to review: {event.title} ({event.reference_number})",
        message,
        settings.ADMIN_NOTIFICATION_EMAIL,
    )


def send_submission_emails(event):
    send_receipt_email(event)
    send_admin_new_event_email(event)


def send_approval_email(event):
    """To the submitter, when the admin approves. Rejecting sends nothing."""
    message = (
        f"Good news. \"{event.title}\" is approved and now shows clearly "
        "on the Streetwise calendar.\n\n"
        f"Reference number: {event.reference_number}"
    )
    return _send(
        f"Your event is live: {event.title}",
        message,
        event.submitter_email,
    )
