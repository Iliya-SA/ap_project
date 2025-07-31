from django.shortcuts import render
from products.models import Product
from orders.models import Order
from django.db.models import Avg

def store_view(request):
    new_products = Product.objects.order_by('-created_at')[:10]

    recommended_products = []
    if request.user.is_authenticated:
        if hasattr(request.user, 'profile') and request.user.profile.skin_type:
            recommended_products = Product.objects.filter(
                skin_type=request.user.profile.skin_type
            ).annotate(
                avg_rating=Avg('comments__rating')
            ).order_by('-avg_rating')[:10]

    favorite_products = []
    if request.user.is_authenticated:
        user_orders = Order.objects.filter(user=request.user)
        favorite_product_ids = (
            user_orders.values_list('items__product', flat=True)
            .distinct()
        )
        favorite_products = Product.objects.filter(id__in=favorite_product_ids)[:10]

    return render(request, 'store/store_home.html', {
        'new_products': new_products,
        'recommended_products': recommended_products,
        'favorite_products': favorite_products,
    })
