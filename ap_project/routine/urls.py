from django.urls import path
from . import views

urlpatterns = [
    # API endpoints (minimal)
    path('quiz/', views.quiz_view, name='quiz_api'),
    path('my/', views.my_routine, name='my_routine_api'),

    # Web pages
    path('', views.routine_home, name='routine_home'),
    path('start/', views.routine_start, name='routine_start'),
]
