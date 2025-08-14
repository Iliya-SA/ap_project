from django.urls import path
from .views import signup_view, signin_view, signout_view, profile_view, edit_profile_view


urlpatterns = [
    path('signup/', signup_view, name='signup'),
    path('signin/', signin_view, name='signin'),
    path('signout/', signout_view, name='signout'),
    path('profile/', profile_view, name='profile'), 
    path('edit-profile/', edit_profile_view, name='edit_profile'),
]