from django.contrib import admin
from .models import Event


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ("title", "start_at", "end_at", "location")
    list_filter = ("start_at",)
    search_fields = ("title", "description", "location")

