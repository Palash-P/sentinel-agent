from django.urls import path

from . import views

urlpatterns = [
    path("analyze/", views.AnalyzeView.as_view(), name="analyze"),
    path("adk/analyze/", views.AdkAnalyzeView.as_view(), name="adk_analyze"),
    path("health/", views.health, name="health"),
    path("incidents/", views.IncidentsView.as_view(), name="incidents"),
]
