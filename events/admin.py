from django.contrib import admin
from .models import Event, Video


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ("reference", "title", "status", "start_at", "time_zone", "submitter_email")
    list_editable = ("status",)
    list_filter = ("status", "start_at")
    search_fields = ("title", "description", "location", "submitter_name", "submitter_email")
    readonly_fields = ("reference", "submission_fingerprint", "created_at")

    @admin.display(description="Reference")
    def reference(self, event):
        return event.reference


@admin.register(Video)
class VideoAdmin(admin.ModelAdmin):
    list_display = ("reference", "status", "submitter_name", "created_at")
    list_editable = ("status",)
    list_filter = ("status", "created_at")
    search_fields = ("youtube_url", "submitter_name", "description")

    @admin.display(description="Reference")
    def reference(self, video):
        return video.reference

