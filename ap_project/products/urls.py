from django.urls import path
from .views import ProductDetailView, ProductCommentsView, AddCommentView 

urlpatterns = [
    path('product/<int:pk>/', ProductDetailView.as_view(), name='product-detail'),
    path('product/<int:pk>/comments/', ProductCommentsView.as_view(), name='product-comments'), 
    path('product/<int:pk>/add-comment/', AddCommentView.as_view(), name='add-comment'),
]
