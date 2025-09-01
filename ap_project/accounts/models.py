from django.db import models
from django.contrib.auth import get_user_model
from django.db import models
from products.models import Product
from django.db.models.signals import post_save
from django.dispatch import receiver
User = get_user_model()

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)

class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)

    skin_type = models.CharField(max_length=50, blank=True)        # نوع پوست
    device_type = models.CharField(max_length=50, blank=True)      # نوع دستگاه کاربر (مثلاً موبایل، دسکتاپ)
    created_at = models.DateTimeField(auto_now_add=True)           # زمان ساخت پروفایل
    favorites = models.ManyToManyField(Product, blank=True, related_name='favorited_by')
    keywords = models.JSONField(blank=True, null=True, default=dict) 
    user_preferences = models.JSONField(blank=True, null=True, default=dict)
    visited_items = models.JSONField(blank=True, null=True, default=list)  # آیتم‌های بازدیدشده توسط کاربر

    def __str__(self):
        return f'Profile of {self.user.username}'

