from django.urls import path

from .views import CategoryListView, EventListCreateView

urlpatterns = [
    path("events/", EventListCreateView.as_view(), name="event-list-create"),
    path("categories/", CategoryListView.as_view(), name="category-list"),
]
