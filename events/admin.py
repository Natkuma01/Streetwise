from django.contrib import admin, messages
from django.db.models import Case, IntegerField, Value, When

from .emails import send_approval_email
from .models import Category, Event


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    search_fields = ["name"]


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = [
        "title",
        "status",
        "start_at",
        "attendance_mode",
        "submitter_email",
        "ref_number",
        "created_at",
    ]
    list_filter = ["status", "attendance_mode", "categories"]
    search_fields = ["title", "ref_number", "submitter_email", "submitter_name"]
    filter_horizontal = ["categories"]
    # manage_key is left out on purpose. It is a secret the admin never needs.
    readonly_fields = ["ref_number", "reminder_sent_at", "created_at", "updated_at"]
    actions = ["approve_events", "reject_events", "cancel_events"]

    def get_ordering(self, request):
        # Pending events first so they are easy to find, then soonest start.
        # Set here because the admin list overrides any order set elsewhere.
        pending_first = Case(
            When(status=Event.Status.PENDING, then=Value(0)),
            default=Value(1),
            output_field=IntegerField(),
        )
        return [pending_first.asc(), "start_at"]

    def save_model(self, request, obj, form, change):
        previous_status = None
        if change:
            previous_status = Event.objects.values_list("status", flat=True).get(pk=obj.pk)
        super().save_model(request, obj, form, change)
        if obj.status == Event.Status.APPROVED and previous_status != Event.Status.APPROVED:
            send_approval_email(obj)

    def _set_status(self, request, queryset, new_status, label):
        changed = 0
        for event in queryset.exclude(status=new_status):
            event.status = new_status
            event.save(update_fields=["status", "updated_at"])
            if new_status == Event.Status.APPROVED:
                send_approval_email(event)
            changed += 1
        self.message_user(request, f"{changed} event(s) {label}.", messages.SUCCESS)

    @admin.action(description="Approve selected events (emails the submitter)")
    def approve_events(self, request, queryset):
        self._set_status(request, queryset, Event.Status.APPROVED, "approved")

    @admin.action(description="Reject selected events (no email)")
    def reject_events(self, request, queryset):
        self._set_status(request, queryset, Event.Status.REJECTED, "rejected")

    @admin.action(description="Cancel selected events (no email)")
    def cancel_events(self, request, queryset):
        self._set_status(request, queryset, Event.Status.CANCELLED, "cancelled")
