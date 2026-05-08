from django.urls import path
from . import views

urlpatterns = [
    path('leak/aws-key/', views.leak_aws_key),
    path('leak/jwt/', views.leak_jwt),
    path('leak/account/', views.leak_account),
    path('leak/db-uri/', views.leak_db_uri),
]
