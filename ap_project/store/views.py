from django.views.decorators.http import require_GET, require_POST
from django.http import JsonResponse
from django.shortcuts import render , redirect
from django.utils import timezone
from products.models import Product, Comment
from orders.models import Order
from django.db.models import Count, Avg, F, FloatField, ExpressionWrapper, Func, Q
from django.db.models.functions import Coalesce, Ln
from django.contrib.auth.decorators import login_required
from context.views import get_persian_season
from rest_framework.test import APIRequestFactory
from django.shortcuts import get_object_or_404
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from products.seasonal_vectors import SEASONAL_VECTORS
from django.db.models import Avg, Count

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

@require_GET
def search_products_json(request):
    query = request.GET.get('q', '').strip()
    sort = request.GET.get('sort', 'newest')
    page = int(request.GET.get('page', 1))
    page_size = 16
    qs = Product.objects.annotate(
        avg_rating=Coalesce(Avg('comments__rating'), 0.0),
        comment_count=Coalesce(Count('comments'), 0)
    )
    if query:
        qs = qs.filter(
            Q(name__icontains=query) |
            Q(category__icontains=query) |
            Q(tags__icontains=query) |
            Q(skin_type__icontains=query)
        )
    if sort == 'newest':
        qs = qs.order_by('-created_at')
    elif sort == 'cheapest':
        qs = qs.order_by('price')
    elif sort == 'expensive':
        qs = qs.order_by('-price')
    elif sort == 'alpha_asc':
        qs = qs.order_by('name')
    elif sort == 'alpha_desc':
        qs = qs.order_by('-name')
    start = (page - 1) * page_size
    end = start + page_size
    products = qs[start:end]
    has_more = qs.count() > end
    data = []
    for p in products:
        data.append({
            'id': p.id,
            'name': p.name,
            'price': p.price,
            'image_url': p.image.url if p.image else '',
            'stock': p.stock,
            'avg_rating': float(getattr(p, 'avg_rating', 0.0)),
        })
    return JsonResponse({'products': data, 'has_more': has_more})
def products_page_view(request):
    return render(request, 'store/all_products.html')
def all_products_view(request):
    sort = request.GET.get('sort', 'newest')
    page = int(request.GET.get('page', 1))
    page_size = 16
    qs = Product.objects.annotate(
        avg_rating=Coalesce(Avg('comments__rating'), 0.0),
        comment_count=Coalesce(Count('comments'), 0)
    )
    if sort == 'newest':
        qs = qs.order_by('-created_at')
    elif sort == 'cheapest':
        qs = qs.order_by('price')
    elif sort == 'expensive':
        qs = qs.order_by('-price')
    elif sort == 'alpha_asc':
        qs = qs.order_by('name')
    elif sort == 'alpha_desc':
        qs = qs.order_by('-name')
    start = (page - 1) * page_size
    end = start + page_size
    products = qs[start:end]
    has_more = qs.count() > end
    data = []
    for p in products:
        data.append({
            'id': p.id,
            'name': p.name,
            'price': p.price,
            'image_url': p.image.url if p.image else '',
            'stock': p.stock,
            'avg_rating': float(getattr(p, 'avg_rating', 0.0)),
        })
    return JsonResponse({'products': data, 'has_more': has_more})
@login_required
def visited_items_json(request):
    profile = getattr(request.user, 'profile', None)
    visited = profile.visited_items if profile else []
    page = int(request.GET.get('page', 1))
    page_size = int(request.GET.get('page_size', 30))
    start = (page - 1) * page_size
    end = start + page_size
    items = visited[::-1][start:end]
    data = []
    for item in items:
        product = Product.objects.filter(id=item.get('product_id')).first()
        if product:
            data.append({
                'product_id': product.id,
                'name': product.name,
                'visit_time': item.get('visit_time'),
                'url': f'/products/{product.id}/'
            })
    has_more = end < len(visited)
    return JsonResponse({'items': data, 'has_more': has_more})
@login_required
@require_POST
def clear_visited_items(request):
    profile = getattr(request.user, 'profile', None)
    if profile:
        profile.visited_items = []
        profile.save()
    return JsonResponse({'success': True})
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
    ).order_by('-created_at')[:12]

    # محصولات پیشنهادی برای پوست کاربر: محصولات با skin_type شامل نوع پوست و avg_rating >= 3.0
    recommended_products = []
    if request.user.is_authenticated and hasattr(request.user, 'profile') and request.user.profile.skin_type:
        skin_type = request.user.profile.skin_type
        # Pick 40 random products matching skin_type and avg_rating >= 3.0
        qs_40 = Product.objects.annotate(
            avg_rating=Coalesce(Avg('comments__rating'), 0.0),
            comment_count=Coalesce(Count('comments'), 0)
        ).filter(
            skin_type__icontains=skin_type,
            avg_rating__gte=3.0
        ).order_by('?')[:40]
        # From those 40, pick 10 at random
        import random
        products_10 = random.sample(list(qs_40), min(10, len(qs_40))) if qs_40 else []
        # Sort by avg_rating descending
        recommended_products = sorted(products_10, key=lambda p: getattr(p, 'avg_rating', 0.0), reverse=True)

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
    # محصولات فصلی با شباهت کسینوسی به توکن‌های فصل
    import numpy as np
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
    from products.seasonal_vectors import SEASONAL_VECTORS

    season = get_persian_season()
    season_map = {'بهار': 'spring', 'تابستان': 'summer', 'پاییز': 'autumn', 'زمستان': 'winter'}
    season_key = season_map.get(season, 'spring')
    season_tokens = SEASONAL_VECTORS.get(season_key, [])

    # Select products with avg_rating >= 3.0, pick up to 40 at random for similarity comparison
    high_rated_qs = Product.objects.annotate(
        avg_rating=Coalesce(Avg('comments__rating'), 0.0),
        comment_count=Coalesce(Count('comments'), 0)
    ).filter(avg_rating__gte=3.0).order_by('?')[:40]
    all_products = list(high_rated_qs)
    def get_product_tokens(product):
        pt = getattr(product, 'products_tokens', {})
        if isinstance(pt, dict):
            if 'tokens' in pt and isinstance(pt['tokens'], list):
                return pt['tokens']
            else:
                tmp = []
                for v in pt.values():
                    if isinstance(v, list):
                        tmp.extend(v)
                return tmp
        elif isinstance(pt, list):
            return pt
        tokens = []
        for field in ['name', 'description', 'brand', 'category']:
            val = getattr(product, field, '')
            if val:
                tokens.append(str(val))
        return tokens

    product_corpus = [" ".join(get_product_tokens(p)) for p in all_products]
    season_text = " ".join(season_tokens)
    vectorizer = TfidfVectorizer()
    X = vectorizer.fit_transform(product_corpus + [season_text])

    similarities = cosine_similarity(X[:-1], X[-1].reshape(1, -1)).ravel()
    top_indices = np.argsort(similarities)[::-1][:10]

    # Ensure products have avg_rating annotated (so template stars show correctly)
    top_ids = [all_products[i].id for i in top_indices] if len(all_products) > 0 else []
    annotated_qs = Product.objects.filter(id__in=top_ids).annotate(
        avg_rating=Coalesce(Avg('comments__rating'), 0.0),
        comment_count=Coalesce(Count('comments'), 0)
    )
    annotated_map = {p.id: p for p in annotated_qs}

    seasonal_products = []
    for i in top_indices:
        # preserve similarity ordering (top_indices is sorted by similarity desc)
        pid = all_products[i].id
        prod = annotated_map.get(pid) or all_products[i]
        # attach similarity score for potential debug/display
        setattr(prod, 'similarity_score', float(similarities[i]))
        # ensure avg_rating is present and numeric (use model/helper as fallback)
        try:
            avg = getattr(prod, 'avg_rating', None)
            if avg is None:
                agg = Comment.objects.filter(product_id=pid).aggregate(avg=Avg('rating'))
                avg = agg.get('avg') if agg else None
                if avg is None:
                    avg = prod.average_rating() if hasattr(prod, 'average_rating') else 0.0
        except Exception:
            avg = 0.0
        try:
            prod.avg_rating = float(avg or 0.0)
        except Exception:
            prod.avg_rating = 0.0
        seasonal_products.append(prod)

    # seasonal_products are returned in descending similarity order; do not re-sort by rating

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

    # Infinite scroll and sorting support
    sort = request.GET.get('sort', 'newest')
    page = int(request.GET.get('page', 1))
    page_size = 16
    qs = Product.objects.filter(q).annotate(
        avg_rating=Coalesce(Avg('comments__rating'), 0.0),
        comment_count=Coalesce(Count('comments'), 0)
    )
    if sort == 'newest':
        qs = qs.order_by('-created_at')
    elif sort == 'cheapest':
        qs = qs.order_by('price')
    elif sort == 'expensive':
        qs = qs.order_by('-price')
    elif sort == 'alpha_asc':
        qs = qs.order_by('name')
    elif sort == 'alpha_desc':
        qs = qs.order_by('-name')
    else:
        qs = qs.order_by('-created_at')
    start = (page - 1) * page_size
    end = start + page_size
    products = qs[start:end]
    has_more = qs.count() > end
    if request.GET.get('json') == '1':
        data = []
        for p in products:
            data.append({
                'id': p.id,
                'name': p.name,
                'price': p.price,
                'image_url': p.image.url if p.image else '',
                'stock': p.stock,
                'avg_rating': float(getattr(p, 'avg_rating', 0.0)),
            })
        return JsonResponse({'products': data, 'has_more': has_more})
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
        results = [{'id': product.id, 'name': product.name} for product in products]
    return JsonResponse(results, safe=False)

@login_required
def visited_items_view(request):
    # صفحه فقط قالب را رندر می‌کند، داده‌ها با JS و AJAX لود می‌شوند
    return render(request, 'store/visited_items.html')

@login_required
def favorites_list_view(request):
    favorite_product_ids = request.user.profile.favorites.values_list('id', flat=True)
    products = Product.objects.filter(id__in=favorite_product_ids).annotate(
        avg_rating=Coalesce(Avg('comments__rating'), 0.0),
        comment_count=Coalesce(Count('comments'), 0)
    )
    return render(request, 'store/favorites_list.html', {'products': products})

def seasonal_products_view(request):

    from products.seasonal_vectors import SEASONAL_VECTORS
    import numpy as np
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity

    season = get_persian_season()
    season_map = {'بهار': 'spring', 'تابستان': 'summer', 'پاییز': 'autumn', 'زمستان': 'winter'}
    season_key = season_map.get(season, 'spring')
    season_tokens = SEASONAL_VECTORS.get(season_key, [])
    # Only consider products with avg_rating >= 3.0
    from django.db.models import Avg, Count
    from django.db.models.functions import Coalesce
    high_rated_qs = Product.objects.annotate(
        avg_rating=Coalesce(Avg('comments__rating'), 0.0),
        comment_count=Coalesce(Count('comments'), 0)
    ).filter(avg_rating__gte=3.0)
    all_products = list(high_rated_qs)
    def get_product_tokens(product):
        pt = getattr(product, 'products_tokens', {})
        if isinstance(pt, dict):
            if 'tokens' in pt and isinstance(pt['tokens'], list):
                return pt['tokens']
            else:
                tmp = []
                for v in pt.values():
                    if isinstance(v, list):
                        tmp.extend(v)
                return tmp
        elif isinstance(pt, list):
            return pt
        tokens = []
        for field in ['name', 'description', 'brand', 'category']:
            val = getattr(product, field, '')
            if val:
                tokens.append(str(val))
        return tokens
    product_corpus = [" ".join(get_product_tokens(p)) for p in all_products]
    season_text = " ".join(season_tokens)
    vectorizer = TfidfVectorizer()
    X = vectorizer.fit_transform(product_corpus + [season_text])
    similarities = cosine_similarity(X[:-1], X[-1].reshape(1, -1)).ravel()
    # Filter products with similarity > 0.1
    filtered = [(p, float(similarities[i])) for i, p in enumerate(all_products) if similarities[i] > 0.1]
    # Sort by similarity descending
    filtered_sorted = sorted(filtered, key=lambda x: x[1], reverse=True)
    # Annotate avg_rating and pass similarity_score
    filtered_ids = [p.id for p, _ in filtered_sorted]
    annotated_qs = Product.objects.filter(id__in=filtered_ids).annotate(
        avg_rating=Coalesce(Avg('comments__rating'), 0.0),
        comment_count=Coalesce(Count('comments'), 0)
    )
    annotated_map = {p.id: p for p in annotated_qs}
    seasonal_products = []
    for pid, sim in zip(filtered_ids, [s for _, s in filtered_sorted]):
        prod = annotated_map.get(pid)
        if prod:
            setattr(prod, 'similarity_score', sim)
            seasonal_products.append(prod)
    return render(request, 'context/seasonal_products.html', {
        'seasonal_products': seasonal_products,
        'season': season
    })


def full_plan(request):
    # categories order: پاک کننده, تونر, مرطوب‌کننده, مرطوب‌کننده, ضدآفتاب (sunscreen last)
    from recommendation.views import build_products_from_db, build_purchases_from_db, get_user_preferences_from_db, compute_recommendations
    cats = [
        ('پاک کننده', ['پاک کننده', 'پاک‌کننده']),
        ('تونر', ['تونر']),
        ('سرم', ['سرم']),
        ('روشن کننده', ['روشن کننده']),
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
    from django.db.models import Avg, Count
    from django.db.models.functions import Coalesce
    for label, queries in cats:
        q = Q()
        for cat in queries:
            q |= Q(category__icontains=cat)
        prods = Product.objects.filter(q)
        # Annotate with score and avg_rating, sort, and take top 10
        prods = prods.annotate(
            avg_rating=Coalesce(Avg('comments__rating'), 0.0),
            comment_count=Coalesce(Count('comments'), 0)
        )
        prods = [p for p in prods if p.id in scored_products]
        for p in prods:
            p.final_score = scored_products.get(p.id, None)
        prods = sorted(prods, key=lambda p: p.final_score if p.final_score is not None else 0, reverse=True)[:10]
        rows.append({'category': label, 'products': prods})

    return render(request, 'store/full_plan.html', {
        'rows': rows,
        'plan_name': 'طرح کامل'
    })

def hydration_plan(request):
    from recommendation.views import build_products_from_db, build_purchases_from_db, get_user_preferences_from_db, compute_recommendations
    cats = [
        ('پاک کننده', ['پاک کننده', 'پاک‌کننده']),
        ('تونر', ['تونر']),
        ('سرم', ['سرم']),
        ('مرطوب‌کننده', ['مرطوب‌کننده', 'مرطوب کننده'])
    ]
    user_id = request.user.username if request.user.is_authenticated else 'u1'
    products = build_products_from_db(user_id=user_id)
    purchases = build_purchases_from_db(user_id=user_id)
    user_prefs, keywords = get_user_preferences_from_db(user_id=user_id)
    recs = compute_recommendations(products, purchases, user_prefs or {}, keywords or {}, user_id=user_id)
    scored_products = {r['product_id']: r['final_score'] for r in recs['recommendations']}
    rows = []
    from django.db.models import Avg, Count
    from django.db.models.functions import Coalesce
    for label, queries in cats:
        q = Q()
        for cat in queries:
            q |= Q(category__icontains=cat)
        prods = Product.objects.filter(q)
        prods = prods.annotate(
            avg_rating=Coalesce(Avg('comments__rating'), 0.0),
            comment_count=Coalesce(Count('comments'), 0)
        )
        prods = [p for p in prods if p.id in scored_products]
        for p in prods:
            p.final_score = scored_products.get(p.id, None)
        prods = sorted(prods, key=lambda p: p.final_score if p.final_score is not None else 0, reverse=True)[:10]
        rows.append({'category': label, 'products': prods})
    return render(request, 'store/hydration_plan.html', {
        'rows': rows,
        'plan_name': 'طرح آبرسان'
    })

def minimal_plan(request):
    from recommendation.views import build_products_from_db, build_purchases_from_db, get_user_preferences_from_db, compute_recommendations
    cats = [
        ('پاک کننده', ['پاک کننده', 'پاک‌کننده']),
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
    from django.db.models import Avg, Count
    from django.db.models.functions import Coalesce
    for label, queries in cats:
        q = Q()
        for cat in queries:
            q |= Q(category__icontains=cat)
        prods = Product.objects.filter(q)
        prods = prods.annotate(
            avg_rating=Coalesce(Avg('comments__rating'), 0.0),
            comment_count=Coalesce(Count('comments'), 0)
        )
        prods = [p for p in prods if p.id in scored_products]
        for p in prods:
            p.final_score = scored_products.get(p.id, None)
        prods = sorted(prods, key=lambda p: p.final_score if p.final_score is not None else 0, reverse=True)[:10]
        rows.append({'category': label, 'products': prods})
    return render(request, 'store/minimal_plan.html', {
        'rows': rows,
        'plan_name': 'طرح مینیمالیستی'
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