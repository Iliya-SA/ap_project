from django.shortcuts import render , redirect
from products.models import Product, Favorite
from orders.models import Order
from django.http import JsonResponse
from django.db.models import Count, Avg, F, FloatField, ExpressionWrapper, Func, Q
from django.db.models.functions import Coalesce, Ln
from django.contrib.auth.decorators import login_required
from .models import SearchHistory
from context.views import get_persian_season
from django.contrib.auth.decorators import login_required
from recommendation.views import top_recommendations
from rest_framework.test import APIRequestFactory


WORD_MAPPING = {
    "کزمو": "کرم",
    "کزم": "کرم",
    "چرپ": "چرب",
    "charb": "چرب",
    "خشك": "خشک",
    "خشگ": "خشک",
    "معمولي": "معمولی",
    "ترکبیی": "ترکیبی",
    "ابرسان":"آبرسان",
    "آب رسان":"آبرسان",
    "آبرسلن":"آبرسان",
}

def fix_word(word):
    return WORD_MAPPING.get(word, word)

def store_view(request):
    query = request.GET.get('q', '').strip()
    if query:
        words = query.split()
        normalized_words = [WORD_MAPPING.get(word, word) for word in words]

        skin_type_q = Q()
        for word in normalized_words:
            skin_type_q |= Q(skin_type__icontains=word)

        other_fields_q = Q()
        for word in normalized_words:
            other_fields_q &= (
                Q(name__icontains=word) |
                Q(category__icontains=word) |
                Q(tags__icontains=word)
            )

        combined_q = skin_type_q | other_fields_q

        search_results = Product.objects.filter(combined_q).annotate(
            avg_rating=Coalesce(Avg('comments__rating'), 0.0),
            comment_count=Coalesce(Count('comments'), 0),
        ).annotate(
            score=F('avg_rating') * Ln(F('comment_count') + 1)
        ).order_by('-score').distinct()

        if not search_results.exists():
            fallback_q = Q()
            for word in normalized_words:
                fallback_q |= Q(category__icontains=word) | Q(name__icontains=word)

            fallback_results = Product.objects.filter(fallback_q).annotate(
                avg_rating=Coalesce(Avg('comments__rating'), 0.0),
                comment_count=Coalesce(Count('comments'), 0),
            ).annotate(
                score=F('avg_rating') * Ln(F('comment_count') + 1)
            ).order_by('-score').distinct()

            return render(request, 'store/search_results.html', {
                'query': query,
                'search_results': fallback_results,
                'notice': 'هیچ محصول دقیقی پیدا نشد؛ اما این محصولات بر اساس دسته‌بندی یا نام مرتبط نمایش داده شده‌اند.'
            })

        if request.user.is_authenticated:
            SearchHistory.objects.create(user=request.user, query=query)

        return render(request, 'store/search_results.html', {
            'query': query,
            'search_results': search_results,
        })

    # محصولات جدید با آنوتیت امتیاز و تعداد کامنت
    new_products = Product.objects.annotate(
        avg_rating=Coalesce(Avg('comments__rating'), 0.0),
        comment_count=Coalesce(Count('comments'), 0)
    ).order_by('-created_at')[:10]

    # محصولات پیشنهادی با آنوتیت
    recommended_products = []
    if request.user.is_authenticated:
        if hasattr(request.user, 'profile') and request.user.profile.skin_type:
            recommended_products = Product.objects.filter(
                skin_type=request.user.profile.skin_type
            ).annotate(
                avg_rating=Coalesce(Avg('comments__rating'), 0.0),
                comment_count=Coalesce(Count('comments'), 0)
            ).order_by('-avg_rating')[:10]

    # محصولات مورد علاقه: دو بخش جدا
    liked_favorites = []
    recent_purchases = []

    if request.user.is_authenticated:
        # 5 محصول که کاربر لایک کرده
        liked_favorites_qs = Favorite.objects.filter(user=request.user).select_related('product').order_by('-created_at')[:5]
        liked_favorites = [fav.product for fav in liked_favorites_qs]

        # 5 محصول آخرین خریدهای کاربر
        user_orders = Order.objects.filter(user=request.user).order_by('-created_at')[:5]
        purchased_products = []
        for order in user_orders:
            purchased_products.extend([item.product for item in order.items.all()])
        # حذف تکراری‌ها (اختیاری)
        seen = set()
        recent_purchases = []
        for prod in purchased_products:
            if prod.id not in seen:
                seen.add(prod.id)
                recent_purchases.append(prod)
            if len(recent_purchases) >= 5:
                break

        # آنوتیت امتیاز و تعداد کامنت برای هر لیست
        def annotate_products(products_list):
            ids = [p.id for p in products_list]
            annotated = Product.objects.filter(id__in=ids).annotate(
                avg_rating=Coalesce(Avg('comments__rating'), 0.0),
                comment_count=Coalesce(Count('comments'), 0)
            )
            # مرتب‌سازی مجدد بر اساس همان ترتیب اصلی
            annotated_dict = {p.id: p for p in annotated}
            return [annotated_dict[id] for id in ids if id in annotated_dict]

        liked_favorites = annotate_products(liked_favorites)
        recent_purchases = annotate_products(recent_purchases)
    season = get_persian_season()
    seasonal_products = Product.objects.filter(tags__contains=[season]).annotate(
        avg_rating=Coalesce(Avg('comments__rating'), 0.0),
        comment_count=Coalesce(Count('comments'), 0)
    ).order_by('-avg_rating')[:10]

    return render(request, 'store/store_home.html', {
        'new_products': new_products,
        'recommended_products': recommended_products,
        'liked_favorites': liked_favorites,
        'seasonal_products': seasonal_products,
        'recent_purchases': recent_purchases,
        'season': season,
    })
    
def category_view(request, name):
    # آنوتیت کردن میانگین امتیاز و تعداد نظرات
    products = Product.objects.filter(category=name).annotate(
        avg_rating=Avg('comments__rating'),
        comment_count=Count('comments'),
    ).annotate(
        score=ExpressionWrapper(
            F('avg_rating') * Func(F('comment_count') + 1, function='LOG'),
            output_field=FloatField()
        )
    ).order_by('-score')[:20]

    return render(request, 'store/category.html', {
        'products': products,
        'category': name,
    })

def contact_feedback_view(request):
    return render(request, 'store/contact_feedback.html')


def autocomplete_search(request):
    query = request.GET.get('q', '').strip()
    results = []

    if query:
        products = Product.objects.filter(
            Q(name__icontains=query) |
            Q(category__icontains=query) |
            Q(skin_type__icontains=query)
        ).distinct()[:10]

        results = [product.name for product in products]

    return JsonResponse(results, safe=False)

@login_required
def search_history_view(request):
    history = SearchHistory.objects.filter(user=request.user).order_by('-timestamp')[:20]
    return render(request, 'store/search_history.html', {'history': history})

@login_required
def favorites_list_view(request):
    favorite_product_ids = request.user.favorites.values_list('product_id', flat=True)
    products = Product.objects.filter(id__in=favorite_product_ids).annotate(
        avg_rating=Coalesce(Avg('comments__rating'), 0.0),
        comment_count=Coalesce(Count('comments'), 0)
    )
    return render(request, 'store/favorites_list.html', {'products': products})

def seasonal_products_view(request):
    season = get_persian_season()
    products = Product.objects.filter(tags__contains=[season]).annotate(
        avg_rating=Coalesce(Avg('comments__rating'), 0.0),
        comment_count=Coalesce(Count('comments'), 0)
    ).order_by('-avg_rating')
    
    return render(request, 'context/seasonal_products.html', {
        'products': products,
        'season': season
    })
@login_required
def quiz_page(request):
    if request.method == "POST":
        skin_type = request.POST.get("skin_type")
        concerns = request.POST.getlist("concerns")  # لیست
        preferences = request.POST.getlist("preferences")

        factory = APIRequestFactory()
        drf_request = factory.post(
            "/api/recommendations/",
            {"skin_type": skin_type, "concerns": concerns, "preferences": preferences},
            format="json"
        )
        drf_request.user = request.user

        response = top_recommendations(drf_request)

        # ✅ بررسی محتوا
        data = response.data
        if "error" in data:
            return render(request, "store/quiz_result.html", {
                "error": data["error"],
                "recommendations": []
            })

        return render(request, "store/quiz_result.html", {
            "recommendations": data.get("recommendations", [])
        })

    return render(request, "store/quiz_page.html")