from django.contrib import admin
from django.http import JsonResponse
from django.urls import path


def health(_request):
    """Cheap endpoint to confirm Django is up and reachable."""
    return JsonResponse({"status": "ok"})


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/health/", health, name="health"),
    # App routes go here.
]
