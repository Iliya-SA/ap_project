from django.urls import path
from .views import ProductDetailView, ProductCommentsView, AddCommentView, toggle_favorite, delete_comment

urlpatterns = [
    path('<int:pk>/', ProductDetailView.as_view(), name='product-detail'),
    path('<int:pk>/comments/', ProductCommentsView.as_view(), name='product-comments'), 
    path('<int:pk>/add-comment/', AddCommentView.as_view(), name='add-comment'),
    path('favorite/<int:product_id>/', toggle_favorite, name='toggle-favorite'),
    path('comment/<int:pk>/delete/', delete_comment, name='delete-comment'),
]
