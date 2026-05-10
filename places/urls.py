from django.urls import path
from . import views

urlpatterns = [
    path('', views.places),
    path('health/', views.health),
    path('<str:place_id>/', views.place_detail),
]
