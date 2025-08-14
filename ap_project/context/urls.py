from django.urls import path
from .views import seasonal_products_view

urlpatterns = [
    path('seasonal-products/', seasonal_products_view, name='seasonal-products-all'),
]