import os, sys, json, django

# راه اندازی محیط جنگو برای اجرا تابع به صورت مستقل
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ap_project.settings")
django.setup()

from recommendation.utils import compute_product_score

user = "u1"
product = 58
output = compute_product_score(user, product)

print(json.dumps(output, ensure_ascii=False, indent=2, default=lambda o: o.item() if hasattr(o, "item") else str(o)))
