from django.contrib import admin
from .models import Event, Video


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ("title", "status", "start_at", "end_at", "location")
    list_editable = ("status",)
    list_filter = ("status", "start_at")
    search_fields = ("title", "description", "location")


@admin.register(Video)
class VideoAdmin(admin.ModelAdmin):
    list_display = ("reference", "status", "submitter_name", "created_at")
    list_editable = ("status",)
    list_filter = ("status", "created_at")
    search_fields = ("youtube_url", "submitter_name", "description")

    @admin.display(description="Reference")
    def reference(self, video):
        return video.reference

