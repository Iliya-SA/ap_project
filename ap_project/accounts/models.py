from django.db import models
from django.contrib.auth import get_user_model

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
    concerns = models.TextField(blank=True)                        # مشکلات پوستی
    references = models.TextField(blank=True)                      # ارجاعات یا رفرنس‌ها 
    preferences = models.TextField(blank=True)   
    device_type = models.CharField(max_length=50, blank=True)      # نوع دستگاه کاربر (مثلاً موبایل، دسکتاپ)
    created_at = models.DateTimeField(auto_now_add=True)           # زمان ساخت پروفایل

    def __str__(self):
        return f'Profile of {self.user.username}'

