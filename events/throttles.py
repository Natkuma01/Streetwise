"""Per-IP rate limits for the public write endpoints.

DRF reads the rates in REST_FRAMEWORK once, when the module loads. These
classes read the rate from Django settings on every request instead, so the
limits can be changed in .env (and in tests) without touching code.
"""

from django.conf import settings
from rest_framework.throttling import SimpleRateThrottle


class SettingsRateThrottle(SimpleRateThrottle):
    """Throttle one IP address, with the rate named by `rate_setting`."""

    rate_setting = None

    def get_rate(self):
        return getattr(settings, self.rate_setting)

    def get_cache_key(self, request, view):
        return self.cache_format % {
            "scope": self.scope,
            "ident": self.get_ident(request),
        }


class EventSubmitThrottle(SettingsRateThrottle):
    """How many events one IP address can submit in an hour."""

    scope = "event_submit"
    rate_setting = "EVENT_SUBMIT_RATE"


class ManageThrottle(SettingsRateThrottle):
    """How many manage-link requests one IP address can make in an hour.

    This is looser than the submit limit. People open the page, edit,
    save and maybe cancel. It mainly stops key guessing.
    """

    scope = "manage"
    rate_setting = "MANAGE_RATE"
