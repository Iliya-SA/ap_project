
# حذف نظر توسط صاحب نظر
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.contrib.auth import REDIRECT_FIELD_NAME
from django.shortcuts import redirect
@require_POST
def delete_comment(request, pk):
    if not request.user.is_authenticated:
        login_url = '/accounts/signin/'
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'error': 'login required'}, status=403)
        return redirect(f"{login_url}?next={request.path}")
    comment = get_object_or_404(Comment, pk=pk)
    # فقط صاحب نظر اجازه حذف دارد
    if hasattr(comment.user, 'id') and comment.user.id == request.user.id:
        comment.delete()
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'success': True})
        messages.success(request, 'نظر شما حذف شد.')
    else:
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'error': 'permission denied'}, status=403)
        messages.error(request, 'شما اجازه حذف این نظر را ندارید.')
    return redirect(request.META.get('HTTP_REFERER', '/'))
from django.views.generic import DetailView
from .models import Product, Comment
from django.views.generic.edit import CreateView
from django.urls import reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render, get_object_or_404
from django.views.generic import DetailView, ListView
from django.db.models import Avg
from django.shortcuts import get_object_or_404, redirect
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from cart.models import Cart, CartItem

class ProductDetailView(DetailView):
    model = Product
    template_name = 'products/product_detail.html'
    context_object_name = 'product'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        product = self.object
        user = self.request.user

        # نظرات اخیر
        context['recent_comments'] = product.comments.order_by('-created_at')[:3]

        # محصولات مشابه بر اساس similar_products
        similar_ids = product.similar_products if product.similar_products else []
        similar_products = Product.objects.filter(id__in=similar_ids)
        context['similar_products'] = similar_products

        # محصولات همان برند با بیشترین میانگین امتیاز
        brand_products = Product.objects.filter(
            brand=product.brand
        ).exclude(id=product.id).annotate(
            avg_rating=Avg('comments__rating')
        ).order_by('-avg_rating')[:5]
        context['brand_products'] = brand_products

        # وضعیت علاقه‌مندی محصول برای کاربر فعلی
        if user.is_authenticated:
            profile = getattr(user, 'profile', None)
            context['is_favorite'] = profile.favorites.filter(id=product.id).exists() if profile else False
            # current quantity of this product in user's cart
            try:
                cart = Cart.objects.get(user=user)
                cart_item = cart.items.filter(product=product).first()
                context['in_cart_quantity'] = cart_item.quantity if cart_item else 0
                context['cart_item_id'] = cart_item.id if cart_item else None
                context['in_cart'] = True if cart_item and getattr(cart_item, 'quantity', 0) > 0 else False
            except Cart.DoesNotExist:
                context['in_cart_quantity'] = 0
                context['cart_item_id'] = None
                context['in_cart'] = False
        else:
            context['is_favorite'] = False
            context['in_cart_quantity'] = 0

        skin_type_str = str(product.skin_type).replace('[','').replace(']','').replace("'", "")
        context['skin_type_str'] = skin_type_str

        return context


class ProductCommentsView(ListView):
    model = Comment
    template_name = 'products/product_comments.html'
    context_object_name = 'comments'

    def get_queryset(self):
        self.product = get_object_or_404(Product, pk=self.kwargs['pk'])
        return Comment.objects.filter(product=self.product).order_by('-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['product'] = self.product
        return context

class AddCommentView(LoginRequiredMixin, CreateView):
    model = Comment
    fields = ['text', 'rating']
    template_name = 'products/add_comment.html'

    def get_object(self, queryset=None):
        return None  # جلوگیری از تلاش برای پیدا کردن Comment موجود


    def form_valid(self, form):
        # Attach user and product, then save
        form.instance.user = self.request.user.profile
        form.instance.product = get_object_or_404(Product, pk=self.kwargs['pk'])
        self.object = form.save()

        # If request is AJAX, return JSON so frontend can update inline without redirect
        if self.request.headers.get('x-requested-with') == 'XMLHttpRequest':
            user_obj = self.object.user.user  # Profile -> User
            return JsonResponse({
                'user': f"{user_obj.first_name} {user_obj.last_name}",
                'text': self.object.text,
                'rating': self.object.rating,
                'created_at': self.object.created_at.strftime('%Y/%m/%d %H:%M')
            }, status=200)

        return redirect(self.get_success_url())

    def get_success_url(self):
        return reverse_lazy('product-detail', kwargs={'pk': self.kwargs['pk']})


@login_required
@require_POST
def toggle_favorite(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    profile = getattr(request.user, 'profile', None)
    is_favorite = False
    if profile:
        if profile.favorites.filter(id=product.id).exists():
            profile.favorites.remove(product)
            is_favorite = False
        else:
            profile.favorites.add(product)
            is_favorite = True
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({'is_favorite': is_favorite})
    return redirect(request.META.get('HTTP_REFERER', 'store'))


