from django.contrib import admin
from .models import Product 

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin) :
    list_display = ('name', 'brand', 'category', 'price', 'stock', 'skin_type')
    search_fields = ('name', 'brand', 'category')
    list_filter = ('category', 'brand', 'skin_type')