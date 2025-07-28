from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from cart.models import Cart
from .models import Order, OrderItem

@login_required
def checkout(request):
    cart = get_object_or_404(Cart, user=request.user)

    if cart.items.count() == 0:
        messages.warning(request, "سبد خرید شما خالی است!")
        return redirect('cart-detail')

    # ایجاد سفارش جدید
    order = Order.objects.create(user=request.user, total_price=cart.total_price())

    # انتقال اقلام سبد خرید به سفارش
    for item in cart.items.all():
        OrderItem.objects.create(
            order=order,
            product=item.product,
            quantity=item.quantity,
            price=item.product.price
        )

    # پاک کردن سبد خرید
    cart.items.all().delete()

    messages.success(request, "سفارش شما با موفقیت ثبت شد!")
    return redirect('order-history')


@login_required
def order_history(request):
    orders = Order.objects.filter(user=request.user).order_by('-created_at')
    return render(request, 'orders/order_history.html', {'orders': orders})

