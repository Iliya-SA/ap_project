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

    if category:
        qs = qs.filter(category=category)
    if skin_fa:
        qs = qs.filter(skin_type=skin_fa)

    preferences = preferences or []

    # preference example: fragrance_free
    if "fragrance_free" in preferences:
        qs = qs.filter(
            Q(tags__contains=["fragrance_free"]) |
            Q(description__icontains="بدون عطر") |
            Q(description__icontains="fragrance")
        )

    # If picking for a specific concern step (treatment)
    if concern:
        # try matching by category first
        cat = CONCERN_TO_CATEGORY.get(concern)
        if cat:
            qs = qs.filter(category=cat)
        else:
            # fallback by concern keyword in description/concerns_targeted
            qs = qs.filter(
                Q(concerns_targeted__icontains=concern) |
                Q(description__icontains=concern)
            )

    # Prefer in-stock and newer products
    qs = qs.filter(stock__gt=0).order_by("-created_at")

    return qs.first()  # None if no match

def select_products_from_quiz(skin_type, concerns, preferences):
    """
    Returns:
    steps: list[ (step_name, product) ]
    plan_name: str
    """
    skin_fa = _map_skin(skin_type)
    concerns = concerns or []
    preferences = preferences or []

    steps = []

    # 1) Base steps: moisturizer + sunscreen
    for step_name, category in BASE_STEPS:
        prod = pick_product(category=category, skin_fa=skin_fa, preferences=preferences)
        if prod:
            steps.append((step_name, prod))

    # 2) Targeted treatment for the TOP concern (first one user selected)
    main_concern = concerns[0] if concerns else None
    if main_concern:
        treatment = pick_product(skin_fa=skin_fa, preferences=preferences, concern=main_concern)
        if treatment:
            steps.append(("Targeted Treatment", treatment))

    # Decide plan_name
    if main_concern and len(steps) >= 3:
        plan_name = "Full Plan"
    elif not main_concern and any(s[0] == "Moisturizer" for s in steps):
        plan_name = "Hydration Plan"
    else:
        plan_name = "Minimalist Plan"

    return steps, plan_name
