from django.urls import include, path
from django.views.generic import TemplateView

from incidents import views as incident_views

urlpatterns = [
    path("", TemplateView.as_view(template_name="index.html"), name="home"),
    path("test-error/", incident_views.test_error, name="test_error"),
    path("api/", include("incidents.urls")),
]
