from django.db.models import Q
from products.models import Product

# English → Persian mappings (incoming quiz uses EN; DB uses FA)
SKIN_MAP = {
    "oily": "چرب",
    "dry": "خشک",
    "normal": "نرمال",
    "combination": "ترکیبی",
    "sensitive": "حساس",
}

CONCERN_TO_CATEGORY = {
    # EN concern -> FA product category (from your Product.CATEGORY_CHOICES)
    "acne": "ضدجوش",
    "wrinkle": "ضدچروک",
    "aging": "ضدچروک",
    "dark_spots": "روشن‌کننده",
    "hyperpigmentation": "روشن‌کننده",
    "pigmentation": "روشن‌کننده",
}

BASE_STEPS = [
    ("Moisturizer", "آبرسان"),   # always try to include
    ("Sunscreen", "ضدآفتاب"),    # always try to include (day)
]

def _map_skin(skin_type):
    # allow Persian already, else map EN→FA; default None
    return SKIN_MAP.get(skin_type, skin_type)

def pick_product(category=None, skin_fa=None, preferences=None, concern=None):
    qs = Product.objects.all()

    # 🔹 فیلتر بر اساس دسته‌بندی
    if category:
        qs = qs.filter(category=category)

    # 🔹 فیلتر بر اساس نوع پوست
    if skin_fa:
        qs = qs.filter(skin_type=skin_fa)

    preferences = preferences or []

    # 🔹 فیلتر بر اساس ترجیحات
    if "fragrance_free" in preferences:
        qs = qs.filter(
            Q(tags__icontains="fragrance_free") |
            Q(tags__icontains="بدون عطر") |
            Q(description__icontains="بدون عطر")
        )

    # 🔹 فیلتر بر اساس نگرانی
    if concern:
        cat = CONCERN_TO_CATEGORY.get(concern)
        if cat:
            qs = qs.filter(category=cat)
        else:
            qs = qs.filter(
                Q(concerns_targeted__icontains=concern) |
                Q(description__icontains=concern)
            )

    # 🔹 فقط محصولات موجود
    qs = qs.filter(stock__gt=0).order_by("-created_at")
    return qs.first()

def select_products_from_quiz(skin_type, concerns, preferences, plan_type=None):
    skin_fa = _map_skin(skin_type)
    concerns = concerns or []
    preferences = preferences or []

    steps = []

    # مراحل پایه
    for step_name, category in BASE_STEPS:
        prod = pick_product(category=category, skin_fa=skin_fa, preferences=preferences)
        if prod:
            steps.append((step_name, prod))

    # درمان هدفمند فقط برای Full و Hydration
    main_concern = concerns[0] if concerns else None
    if main_concern and plan_type in ["Full Plan", "Hydration Plan"]:
        treatment = pick_product(skin_fa=skin_fa, preferences=preferences, concern=main_concern)
        if treatment:
            steps.append(("Targeted Treatment", treatment))

    # تعیین نام پلن
    if main_concern and len(steps) >= 3:
        plan_name = "Full Plan"
    elif not main_concern and any(s[0] == "Moisturizer" for s in steps):
        plan_name = "Hydration Plan"
    else:
        plan_name = "Minimalist Plan"

    return steps, plan_name
