from django.db import models
from django.db.models import Avg
from django.core.validators import MinValueValidator, MaxValueValidator


class Product(models.Model):
    name = models.CharField(max_length = 100)
    brand = models.CharField(max_length = 100)
    CATEGORY_CHOICES = [
    ('کرم آبرسان', 'کرم آبرسان'),
    ('کرم ضدآفتاب', 'کرم ضدآفتاب'),
    ('کرم ضدچروک', 'کرم ضدچروک'),
    ('کرم روشن‌کننده', 'کرم روشن‌کننده'),
    ('کرم ضدجوش', 'کرم ضدجوش'),
    ('کرم شب', 'کرم شب'),
]
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES)
    description = models.TextField()
    skin_types = models.CharField(max_length=100)
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
