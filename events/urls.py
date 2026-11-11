from django.urls import path
from . import views

urlpatterns = [
    path("events/", views.event_list, name="event-list"),
    path("categories/", views.category_list, name="category-list"),
]

