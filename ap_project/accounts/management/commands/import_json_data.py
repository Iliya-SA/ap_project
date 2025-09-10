"""

DROP DATABASE ap_project;
CREATE DATABASE ap_project CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

cd ap_project
python manage.py makemigrations
python manage.py migrate
python manage.py import_json_data
python manage.py populate_seasonal_keywords

needs reconnect in my sql

username='u1', password='testpass'

"""


from django.core.management.base import BaseCommand
import os
import json
from django.conf import settings
from django.contrib.auth import get_user_model
from products.models import Product
from accounts.models import Profile
from orders.models import Order, OrderItem

class Command(BaseCommand):
    help = "Import products, purchases, and user data from JSON files"

    def handle(self, *args, **kwargs):
        # 1. حذف دیتابیس
        db_path = os.path.join(settings.BASE_DIR, 'db.sqlite3')
        if os.path.exists(db_path):
            os.remove(db_path)
            print("Database deleted.")

        # 2. اجرای migrations
        os.system('python manage.py migrate')

        # 3. بارگذاری داده‌ها
        def load_json(path):
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)

        # مسیر اصلی (دایرکتوری فعلی پروژه)
        BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

        # ساختن مسیرهای نسبی
        products_data = load_json(os.path.join(BASE_DIR, "Test", "products.json"))["products"]
        user_prefs = load_json(os.path.join(BASE_DIR, "Test", "user_preferences.json"))
        keywords = load_json(os.path.join(BASE_DIR, "Test", "keywords.json"))
        purchases = load_json(os.path.join(BASE_DIR, "Test", "purchases.json"))

        User = get_user_model()
        user = User.objects.create_user(
            username='u1',
            password='testpass',
            first_name='کاربر',
            last_name='اولیه',
            email='u1@example.com'
        )
        profile = Profile.objects.get(user=user)
        # مقداردهی فیلدهای skin_type و concerns از user_preferences.json
        if user_prefs:
            profile.skin_type = user_prefs.get('skin_type', '')
            profile.user_preferences = user_prefs
        if keywords:
            profile.keywords = keywords
        # مقداردهی visited_items با قالب صحیح
        visited_items = []
        for pdata in products_data:
            pid = pdata.get('id')
            for visit_time in pdata.get('visit_times', []):
                visited_items.append({"product_id": pid, "visit_time": visit_time})
        profile.visited_items = visited_items
        profile.save()

        # 4. افزودن محصولات
        from products.models import Comment
        # بارگذاری داده‌های مشابه و توکن‌ها
        similar_data = load_json(os.path.join(BASE_DIR, "Test", "similar_products.json"))
        products_tokens_map = similar_data.get('products_tokens', {})
        similar_products_map = similar_data.get('similar_products', {})
        similarity_threshold = similar_data.get('similarity_threshold', 0.4)

        product_map = {}
        for pdata in products_data:
            pid = str(pdata.get('id'))
            # مقداردهی concerns_targeted از suitable_for
            concerns_targeted = ''
            suitable_for = pdata.get('suitable_for', [])
            if suitable_for:
                if isinstance(suitable_for, list):
                    concerns_targeted = ', '.join([str(c) for c in suitable_for])
                else:
                    concerns_targeted = str(suitable_for)
            # مقداردهی products_tokens و similar_products از فایل مشابه
            products_tokens = products_tokens_map.get(pid, {})
            similar_products = similar_products_map.get(pid, [])

            product = Product.objects.create(
                name=pdata.get('name', ''),
                brand=pdata.get('brand', ''),
                category=pdata.get('category', ''),
                description=pdata.get('description', ''),
                skin_type=pdata.get('skin_type', ''),
                suitable_for=suitable_for,
                concerns_targeted=concerns_targeted,
                tags=pdata.get('tags', []),
                price=pdata.get('price', 0),
                stock=pdata.get('stock', 0),
                products_tokens=products_tokens,
                similar_products=similar_products,
                similarity_threshold=similarity_threshold,
            )
            product_map[pdata['id']] = product
            # ثبت امتیاز کاربر به عنوان کامنت
            rating = int(round(float(pdata.get('rating', 3))))
            rating = max(1, min(5, rating))
            Comment.objects.create(
                product=product,
                user=profile,
                text='امتیاز کاربر اولیه',
                rating=rating
            )
            # ثبت علاقه‌مندی‌ها
            if pdata.get('is_favorite'):
                profile.favorites.add(product)

        # 5. افزودن خریدها
        for p in purchases:
            product = product_map.get(p['productId'])
            if product:
                order = Order.objects.create(user=user)
                OrderItem.objects.create(
                    order=order,
                    product=product,
                    quantity=p['quantity'],
                    price=product.price,
                    date=p['date']
                )

        print("Data imported successfully.")