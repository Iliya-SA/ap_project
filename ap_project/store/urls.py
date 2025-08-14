from django.urls import path
from .views import store_view, search_history_view, contact_feedback_view, favorites_list_view, seasonal_products_view
from . import views

urlpatterns = [
    path('', store_view, name='store'),
    path('', store_view, name='home'),
    path('category/<str:name>/', views.category_view, name='category'),
    path('contact-feedback/', contact_feedback_view, name='contact_feedback'),  
    path('autocomplete/', views.autocomplete_search, name='autocomplete_search'),
    path('history/', search_history_view, name='search_history'),
    path('favorites/', favorites_list_view, name='favorites-list'),
    path('seasonal-products/', seasonal_products_view, name='seasonal-products'),
]
