from django.contrib import admin
from django.contrib.auth.models import User
from django.contrib.auth.admin import UserAdmin

# حذف نسخه‌ی پیش‌فرض UserAdmin
admin.site.unregister(User)

# ثبت دوباره User با تنظیمات سفارشی
@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'first_name', 'last_name', 'is_staff', 'is_active', 'is_superuser')
    search_fields = ('username', 'first_name', 'last_name')
    list_filter = ('is_staff', 'is_active', 'is_superuser')

