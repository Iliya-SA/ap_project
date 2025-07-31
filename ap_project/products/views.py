from django.views.generic import DetailView
from .models import Product, Comment
from django.views.generic.edit import CreateView
from django.urls import reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render, get_object_or_404
from django.views.generic import DetailView, ListView
from django.db.models import Avg

class ProductDetailView(DetailView):
    model = Product
    template_name = 'products/product_detail.html'
    context_object_name = 'product'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        product = self.object

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

        return context

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
        form.instance.user = self.request.user.profile
        form.instance.product = get_object_or_404(Product, pk=self.kwargs['pk'])
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy('product-detail', kwargs={'pk': self.kwargs['pk']})
