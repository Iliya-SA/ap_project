from django.db import models
from django.db.models import Avg
from django.core.validators import MinValueValidator, MaxValueValidator
from django.contrib.auth.models import User

class Product(models.Model):
    name = models.CharField(max_length = 100)
    brand = models.CharField(max_length = 100)
    CATEGORY_CHOICES = [
    ('آبرسان', 'آبرسان'),
    ('ضدآفتاب', 'ضدآفتاب'),
    ('ضدچروک', 'ضدچروک'),
    ('روشن‌کننده', 'روشن‌کننده'),
    ('ضدجوش', 'ضدجوش'),
    ('کرم شب', 'کرم شب'),
]
    SKIN_TYPE_CHOICES = [
    ('خشک', 'خشک'),
    ('چرب', 'چرب'),
    ('نرمال', 'نرمال'),
    ('ترکیبی', 'ترکیبی'),
    ('حساس', 'حساس'),
]
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES)
    description = models.TextField()
    skin_type = models.CharField(max_length=50, choices=SKIN_TYPE_CHOICES)
    concerns_targeted = models.CharField(max_length=200)
    tags = models.JSONField(default=list)
    price = models.IntegerField()
    stock = models.PositiveIntegerField(default=0)
    image = models.ImageField(upload_to='product_images/', default='product_images/default.jpg')
    created_at = models.DateTimeField(auto_now_add=True)

    def average_rating(self):
        result = self.comments.aggregate(avg_rating=Avg('rating'))
        return result['avg_rating'] or 0  # اگر کامنت نبود صفر برمی‌گردونه
    def __str__(self):
        return f"{self.name} ({self.brand})"

class Comment(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='comments')
    user = models.ForeignKey('accounts.Profile', on_delete=models.CASCADE)  
    text = models.TextField()
    rating = models.PositiveSmallIntegerField(
    validators=[MinValueValidator(1), MaxValueValidator(5)]
)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user} - {self.product.name} ({self.rating})"


class Favorite(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='favorites')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='favorited_by')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'product')  # جلوگیری از تکرار علاقه‌مندی

    def __str__(self):
        return f"{self.user.username} ❤️ {self.product.name}"