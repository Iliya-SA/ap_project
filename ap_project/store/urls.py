from django.urls import path
from .views import (
    store_view, visited_items_view, contact_feedback_view,
    favorites_list_view, seasonal_products_view, routine
)
from .views import all_products_view, products_page_view
from . import views

urlpatterns = [
    path('', store_view, name='store'),
    path('', store_view, name='home'),
    path('category/<str:name>/', views.category_view, name='category'),
    path('contact-feedback/', contact_feedback_view, name='contact_feedback'),  
    path('autocomplete/', views.autocomplete_search, name='autocomplete_search'),
    path('favorites/', favorites_list_view, name='favorites-list'),
    path('seasonal-products/', seasonal_products_view, name='seasonal-products'),
    path('visited-items/', visited_items_view, name='visited-items'),
    path("routine/", routine, name="routine"),
    path("routine/full-plan/", views.full_plan, name="full_plan"),
    path("routine/hydration-plan/", views.hydration_plan, name="hydration_plan"),
    path("routine/minimal-plan/", views.minimal_plan, name="minimal_plan"),
    path('products/', products_page_view, name='products-page'),
    path('products/all/', all_products_view, name='all-products'),
]
