from django.urls import path
from . import views

urlpatterns = [
    path('report/<int:company_id>/', views.report),
    path('dashboard/<int:company_id>/', views.dashboard),
]
