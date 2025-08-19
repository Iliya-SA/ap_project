# recommendation/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('top/', views.top_recommendations, name='top_recommendations'),
]