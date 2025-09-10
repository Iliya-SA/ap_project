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

        # محصولات مرتبط با همان نوع پوست (skin_type) با بیشترین میانگین امتیاز
        related_products = Product.objects.filter(
            skin_type=product.skin_type
        ).exclude(id=product.id).annotate(
            avg_rating=Avg('comments__rating')
        ).order_by('-avg_rating')[:5]
        context['related_products'] = related_products

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
        else:
            context['is_favorite'] = False

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
            return JsonResponse({
                'user': str(self.object.user),
                'text': self.object.text,
                'rating': self.object.rating,
                'created_at': self.object.created_at.strftime('%Y/%m/%d %H:%M')
            })

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


