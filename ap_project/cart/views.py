from django.shortcuts import render
from django.shortcuts import redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from products.models import Product
from .models import Cart, CartItem
from orders.models import Order, OrderItem
@login_required
def cart_detail(request):
    cart, created = Cart.objects.get_or_create(user=request.user)
    return render(request, 'cart/cart_detail.html', {'cart': cart})


@login_required
def add_to_cart(request, pk):
    product = get_object_or_404(Product, pk=pk)
    cart, created = Cart.objects.get_or_create(user=request.user)

    # اگر محصول از قبل تو سبد خرید باشه، تعدادش زیاد میشه
    cart_item, created = CartItem.objects.get_or_create(cart=cart, product=product)
    if not created:
        cart_item.quantity += 1
        cart_item.save()

    return redirect('cart-detail')

@login_required
def update_cart(request):
    if request.method == 'POST':
        cart = Cart.objects.get(user=request.user)
        for key, value in request.POST.items():
            if key.startswith('quantity_'):
                item_id = key.split('_')[1]
                try:
                    item = CartItem.objects.get(id=item_id, cart=cart)
                    quantity = int(value)
                    if quantity > 0:
                        item.quantity = quantity
                        item.save()
                    else:
                        item.delete()
                except CartItem.DoesNotExist:
                    pass
        return redirect('cart-detail')
    return redirect('cart-detail')
@login_required
def checkout(request):
    if request.method == "POST":
        # اینجا میتونی منطق ذخیره‌سازی سفارش یا پاک کردن سبد خرید رو بذاری
        # الان فقط به عنوان نمونه سبد رو خالی می‌کنیم یا کاربر رو به صفحه تشکر هدایت می‌کنیم

        cart = Cart.objects.get(user=request.user)
        cart.items.all().delete()  # آیتم‌ها رو حذف میکنه (می‌تونی تغییر بدی)

        # هدایت به صفحه تشکر یا صفحه اصلی
        return redirect('home')  # آدرس صفحه اصلی یا صفحه تشکر
    else:
        return redirect('cart-detail')
    
@login_required
def checkout(request):
    cart = Cart.objects.get(user=request.user)

    if cart.items.count() == 0:
        return redirect('cart-detail')

    # سفارش جدید بسازیم
    order = Order.objects.create(user=request.user)

    # آیتم‌های سبد خرید رو به سفارش منتقل کنیم
    for item in cart.items.all():
        OrderItem.objects.create(
            order=order,
            product=item.product,
            quantity=item.quantity,
            price=item.product.price
        )

    # سبد خرید رو خالی کنیم
    cart.items.all().delete()

    # انتقال به صفحه تاریخچه سفارش‌ها
    return redirect('order-history')