from django.urls import path
from . import views

urlpatterns = [
    path('register/', views.register_credential),
    path('use/', views.use_credential),
    path('audit/', views.audit_log),
    path('<str:client_id>/', views.list_credentials),
]
