from django.urls import path
from .views import quiz_view, my_routine

urlpatterns = [
    path('quiz/', quiz_view, name='quiz_api'),
    path('my/', my_routine, name='my_routine'),
]
