from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from products.models import Product
from accounts.models import Profile

SKIN_TYPE_MAP = {
    "oily": "چرب",
    "dry": "خشک",
    "normal": "نرمال",
    "combination": "ترکیبی",
    "sensitive": "حساس"
}

CONCERN_MAP = {
    "acne": "ضدجوش",
    "redness": "قرمزی",
    "dullness": "کدری",
    "aging": "ضدچروک",
    "dark_spots": "روشن‌کننده"
}

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def top_recommendations(request):
    data = request.data
    skin_type_en = data.get("skin_type", "").lower()
    concerns_en = data.get("concerns", [])
    preferences = data.get("preferences", [])

    skin_type_fa = SKIN_TYPE_MAP.get(skin_type_en)
    if not skin_type_fa:
        return Response({"error": "نوع پوست نامعتبر است."}, status=400)

    concerns_fa = [CONCERN_MAP.get(c.lower(), c) for c in concerns_en]

    qs = Product.objects.all()
    qs = qs.filter(skin_type=skin_type_fa)

    if concerns_fa:
        for concern in concerns_fa:
            qs = qs.filter(concerns_targeted__icontains=concern)

    # ترجیحات (مثل fragrance_free)
    # if preferences:
    #     for pref in preferences:
    #         if "free" in pref:
    #             qs = qs.exclude(tags__icontains=pref)

    products = qs[:5]
    results = []

    for p in products:
        reason = f"مناسب برای پوست {skin_type_fa}"
        if any(c in (p.concerns_targeted or "") for c in concerns_fa):
            reason += f" و مشکلات {', '.join(concerns_fa)}"
        if preferences:
            reason += f" و ترجیحات: {', '.join(preferences)}"

        results.append({
            "product_id": p.id,
            "name": p.name,
            "brand": p.brand,
            "price": float(p.price),
            "image_url": p.image.url if p.image else None,
            "score": 1,
            "reason": reason
        })

    return Response({"recommendations": results})