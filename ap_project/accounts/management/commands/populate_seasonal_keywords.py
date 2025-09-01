"""

cd ap_project
python manage.py populate_seasonal_keywords

"""

from django.core.management.base import BaseCommand
from recommendation.models import SeasonalKeyword

class Command(BaseCommand):
    help = "Populate SeasonalKeyword table with default seasonal keywords"

    def handle(self, *args, **options):
        seasonal_map = {
            "spring": ["سبک", "جذب سریع", "روشن‌کننده", "لایه‌بردار", "آنتی‌اکسیدان", "ویتامین C"],
            "summer": ["ضد آفتاب", "جذب سریع", "سبک", "مات‌کننده", "بدون الکل", "محافظت"],
            "autumn": ["مرطوب‌کننده", "تغذیه‌کننده", "بازسازی", "ضدچروک", "آبرسان", "پپتید"],
            "winter": ["تغذیه‌کننده", "مغذی", "شب", "روغن", "محافظ", "آبرسان"]
        }

        for season, keywords in seasonal_map.items():
            for kw in keywords:
                obj, created = SeasonalKeyword.objects.get_or_create(season=season, keyword=kw)
                if created:
                    self.stdout.write(self.style.SUCCESS(f"Added: {season} - {kw}"))
                else:
                    self.stdout.write(f"Exists: {season} - {kw}")
