from django.urls import path
from . import views

urlpatterns = [
    path('', views.cart_detail, name='cart-detail'),
    path('add/<int:pk>/', views.add_to_cart, name='add-to-cart'),
    path('update/', views.update_cart, name='update-cart'),  
    path('checkout/', views.checkout, name='checkout'),
      
]