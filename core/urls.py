from django.urls import path
from . import views
urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("health/", views.health, name="health"),
    path("register/", views.register, name="register"),
    path("tasks/", views.task_list, name="tasks"),
    path("tasks/<int:pk>/status/", views.set_status, name="task_status"),
    path("tasks/<int:pk>/edit/", views.task_edit, name="task_edit"),
    path("tasks/<int:pk>/delete/", views.task_delete, name="task_delete"),
    path("settings/", views.settings_view, name="settings"),
    path("export.csv", views.export_csv, name="export_csv"),
]
