from django.shortcuts import render
from django.shortcuts import redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from products.models import Product
from .models import Cart, CartItem
from orders.models import Order, OrderItem
from django.http import JsonResponse
@login_required
def cart_detail(request):
    cart, created = Cart.objects.get_or_create(user=request.user)
    return render(request, 'cart/cart_detail.html', {'cart': cart})


@login_required
def add_to_cart(request, pk):
    product = get_object_or_404(Product, pk=pk)
    cart, created = Cart.objects.get_or_create(user=request.user)

    # اگر محصول از قبل تو سبد خرید باشه، تعدادش زیاد میشه
    # support optional quantity parameter (from product page)
    qty = 1
    try:
        if request.method == 'POST':
            qty = int(request.POST.get('quantity', 1))
        else:
            # AJAX from product page may be POST with headers; allow GET fallback
            qty = int(request.GET.get('quantity', 1))
    except (ValueError, TypeError):
        qty = 1

    cart_item, created = CartItem.objects.get_or_create(cart=cart, product=product)
    if created:
        cart_item.quantity = max(1, qty)
    else:
        cart_item.quantity += max(1, qty)
    cart_item.save()

    # If request is AJAX (X-Requested-With header), return JSON so front-end can show a toast
    requested_with = request.META.get('HTTP_X_REQUESTED_WITH') or request.headers.get('x-requested-with')
    if requested_with == 'XMLHttpRequest':
        return JsonResponse({
            'success': True,
            'cart_count': cart.items.count(),
            'item_id': cart_item.id,
            'item_quantity': cart_item.quantity,
        })

    return redirect('cart-detail')

@login_required
def update_cart(request):
    if request.method == 'POST':
        cart = Cart.objects.get(user=request.user)
        updated_item_info = None
        for key, value in request.POST.items():
            if key.startswith('quantity_'):
                item_id = key.split('_')[1]
                try:
                    item = CartItem.objects.get(id=item_id, cart=cart)
                    quantity = int(value)
                    if quantity > 0:
                        item.quantity = quantity
                        item.save()
                        updated_item_info = {
                            'item_id': item.id,
                            'item_total': int(item.total_price()) if hasattr(item, 'total_price') else int(item.quantity * item.product.price),
                            'item_quantity': item.quantity,
                        }
                    else:
                        item.delete()
                        updated_item_info = {
                            'item_id': int(item_id),
                            'item_total': 0
                        }
                except (CartItem.DoesNotExist, ValueError):
                    pass

        # If AJAX, return JSON with updated totals so frontend can update UI in-place
        requested_with = request.META.get('HTTP_X_REQUESTED_WITH') or request.headers.get('x-requested-with')
        if requested_with == 'XMLHttpRequest':
            # cart.total_price may be Decimal; send as int for display (تومان)
            try:
                cart_total = int(cart.total_price)
            except Exception:
                # fallback: compute from items
                cart_total = sum(int(i.total_price()) if hasattr(i, 'total_price') else int(i.quantity * i.product.price) for i in cart.items.all())

            resp = {'cart_total': cart_total}
            if updated_item_info:
                resp.update(updated_item_info)
            return JsonResponse(resp)

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

    # If quantities were sent in POST (e.g., user adjusted counts before checkout), update them
    if request.method == 'POST':
        for key, value in request.POST.items():
            if key.startswith('quantity_'):
                item_id = key.split('_', 1)[1]
                try:
                    item = CartItem.objects.get(id=item_id, cart=cart)
                    quantity = int(value)
                    if quantity > 0:
                        item.quantity = quantity
                        item.save()
                    else:
                        item.delete()
                except (CartItem.DoesNotExist, ValueError):
                    pass

    if cart.items.count() == 0:
        return redirect('cart-detail')

    # سفارش جدید بسازیم
    # Order model doesn't store total_price as a field; compute via order.total_price() when needed
    order = Order.objects.create(user=request.user)

    # آیتم‌های سبد خرید رو به سفارش منتقل کنیم
    for item in cart.items.all():
        # کم کردن موجودی محصول
        product = item.product
        if product.stock >= item.quantity:
            product.stock -= item.quantity
            product.save()
        else:
            # اگر موجودی کافی نبود، می‌توان پیام خطا یا هندل مناسب اضافه کرد
            continue
        OrderItem.objects.create(
            order=order,
            product=product,
            quantity=item.quantity,
            price=product.price
        )

    # سبد خرید رو خالی کنیم
    cart.items.all().delete()

    # انتقال به صفحه تاریخچه سفارش‌ها
    return redirect('order-history')