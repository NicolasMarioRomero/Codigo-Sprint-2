from django.urls import path
from . import views

urlpatterns = [
    path('extract/', views.trigger_extraction),
    path('extract/<str:task_id>/', views.task_status),
]
