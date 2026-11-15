from django.urls import path
from . import views

urlpatterns = [
    path("events/", views.event_list, name="event-list"),
    path("events/<int:event_id>/", views.event_detail, name="event-detail"),
    path("categories/", views.category_list, name="category-list"),
]

