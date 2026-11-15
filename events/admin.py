from django.contrib import admin
from .models import Event


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ("title", "status", "start_at", "end_at", "location")
    list_editable = ("status",)
    list_filter = ("status", "start_at")
    search_fields = ("title", "description", "location")

