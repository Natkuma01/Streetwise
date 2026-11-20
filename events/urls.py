from django.urls import path

from .views import CategoryListView, EventListCreateView, ManageCancelView, ManageEventView

urlpatterns = [
    path("events/", EventListCreateView.as_view(), name="event-list-create"),
    path("categories/", CategoryListView.as_view(), name="category-list"),
    path("manage/", ManageEventView.as_view(), name="manage-event"),
    path("manage/cancel/", ManageCancelView.as_view(), name="manage-cancel"),
]
