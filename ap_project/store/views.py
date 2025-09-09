from django.shortcuts import render , redirect
from django.utils import timezone
from products.models import Product
from orders.models import Order
from django.http import JsonResponse
from django.db.models import Count, Avg, F, FloatField, ExpressionWrapper, Func, Q
from django.db.models.functions import Coalesce, Ln
from django.contrib.auth.decorators import login_required
from context.views import get_persian_season
from django.contrib.auth.decorators import login_required
from rest_framework.test import APIRequestFactory
from django.shortcuts import get_object_or_404


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
            profile = getattr(request.user, 'profile', None)
            if profile is not None:
                visited = profile.visited_items or []
                # اگر query یک محصول باشد، باید product_id و زمان را ذخیره کنیم
                product_id = None
                if search_results.exists():
                    product_id = search_results.first().id
                visit_time = timezone.now().strftime('%Y-%m-%dT%H:%M:%S')
                if product_id:
                    visited.append({"product_id": product_id, "visit_time": visit_time})
                profile.visited_items = visited[-100:]
                profile.save()

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
    if request.user.is_authenticated and hasattr(request.user, 'profile'):
        liked_favorites = list(request.user.profile.favorites.all())
    else:
        liked_favorites = []
    recent_purchases = []

    if request.user.is_authenticated:
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
    # جستجو با معادل‌های مختلف (نیم‌فاصله، فاصله، بدون فاصله)
    alt_names = [name]
    if '‌' in name:  # نیم‌فاصله
        alt_names.append(name.replace('‌', ' '))
        alt_names.append(name.replace('‌', ''))
    elif ' ' in name:
        alt_names.append(name.replace(' ', ''))
        alt_names.append(name.replace(' ', '‌'))
    else:
        # اگر هیچ فاصله‌ای نیست، معادل با فاصله و نیم‌فاصله را هم اضافه کن
        for i in range(1, len(name)):
            alt_names.append(name[:i] + ' ' + name[i:])
            alt_names.append(name[:i] + '‌' + name[i:])

    q = Q()
    for n in set(alt_names):
        q |= Q(category=n)

    products = Product.objects.filter(q).annotate(
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
def visited_items_view(request):
    profile = getattr(request.user, 'profile', None)
    visited = profile.visited_items if profile else []
    # Get product info for each visited item
    visited_products = []
    for item in visited[::-1][:20]:
        product = Product.objects.filter(id=item.get('product_id')).first()
        if product:
            visited_products.append({
                'product_id': product.id,
                'name': product.name,
                'visit_time': item.get('visit_time'),
                'url': f'/products/{product.id}/'  # Now matches new URL pattern
            })
    return render(request, 'store/visited_items.html', {'visited_items': visited_products})

@login_required
def favorites_list_view(request):
    favorite_product_ids = request.user.profile.favorites.values_list('id', flat=True)
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


def full_plan(request):
    # categories order: پاک کننده, تونر, مرطوب‌کننده, مرطوب‌کننده, ضدآفتاب (sunscreen last)
    from recommendation.views import build_products_from_db, build_purchases_from_db, get_user_preferences_from_db, compute_recommendations
    cats = [
        ('پاک کننده', ['پاک کننده', 'پاک‌کننده']),
        ('تونر', ['تونر']),
        ('مرطوب‌کننده', ['مرطوب‌کننده', 'مرطوب کننده']),
        ('مرطوب‌کننده', ['مرطوب‌کننده', 'مرطوب کننده']),
        ('ضدآفتاب', ['ضدآفتاب', 'ضد آفتاب'])
    ]
    user_id = request.user.username if request.user.is_authenticated else 'u1'
    products = build_products_from_db(user_id=user_id)
    purchases = build_purchases_from_db(user_id=user_id)
    user_prefs, keywords = get_user_preferences_from_db(user_id=user_id)
    recs = compute_recommendations(products, purchases, user_prefs or {}, keywords or {}, user_id=user_id)
    scored_products = {r['product_id']: r['final_score'] for r in recs['recommendations']}
    rows = []
    for label, queries in cats:
        q = Q()
        for cat in queries:
            q |= Q(category__icontains=cat)
        prods = Product.objects.filter(q)
        # Annotate with score, sort, and take top 10
        prods = [p for p in prods if p.id in scored_products]
        for p in prods:
            p.final_score = scored_products.get(p.id, None)
        prods = sorted(prods, key=lambda p: p.final_score if p.final_score is not None else 0, reverse=True)[:10]
        rows.append({'category': label, 'products': prods})

    return render(request, 'store/full_plan.html', {
        'rows': rows,
        'plan_name': 'طرح کامل'
    })
@login_required
def routine(request):
    if request.method == "POST":
        # If POST arrives from some form on the routine page we don't render a separate result page here.
        # The quiz view handles saving and redirecting back via its 'next' parameter.
        # Keep the POST handling minimal and redirect back to routine (or caller) to avoid a separate result page.
        return redirect('routine')

    # GET -> render the routine selection page
    return render(request, "store/routine.html")