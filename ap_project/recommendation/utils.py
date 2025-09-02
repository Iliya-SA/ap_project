# utils.py
import math
import random
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from hazm import Normalizer, word_tokenize, Stemmer

# مدل‌ها - مسیر‌ها را بر اساس پروژه‌تان تنظیم کنید
from products.models import Product
from accounts.models import Profile
from orders.models import OrderItem
from recommendation.models import SeasonalKeyword
from products.models import Comment

random.seed(12345)
normalizer = Normalizer()
stemmer = Stemmer()

# -- پارامترها (همان‌هایی که در recommendation_pipeline.py بودند)
SIM_THRESHOLD = 0.4
KAPPA = 1.0
HALF_LIFE_VISITS = 14.0
HALF_LIFE_BUY = 60.0
LAMBDA_V = math.log(2) / HALF_LIFE_VISITS
LAMBDA_BUY = math.log(2) / HALF_LIFE_BUY

# weights
W_T = 0.30
W_S = 0.10
W_VSIM = 0.20
W_VRATIO = 0.10
W_R = 0.30

BETA_FAV = 0.25
BETA_BUY = 0.40

FORBIDDEN_PENALTY_CAP = 0.25
FORBIDDEN_PER_MATCH = 0.06

USER_ID_DEFAULT = "u1"

# ---------------- کمک‌تابع‌ها ----------------

def to_datetime(tstr):
    # قبول ISO format و تبدیل به offset-naive
    try:
        dt = datetime.fromisoformat(tstr)
    except Exception:
        for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
            try:
                dt = datetime.strptime(tstr, fmt)
                break
            except Exception:
                continue
        else:
            raise ValueError("Unknown date format: " + str(tstr))
    # اگر tzinfo داشت، حذفش کن
    if dt.tzinfo is not None:
        dt = dt.replace(tzinfo=None)
    return dt

def days_between(now_dt, past_dt):
    delta = now_dt - past_dt
    return delta.total_seconds() / (3600 * 24)

def normalize_and_tokenize(text: str) -> List[str]:
    if not text:
        return []
    s = normalizer.normalize(str(text))
    import re
    s = re.sub(r"[^\w\s\u0600-\u06FF]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    toks = word_tokenize(s)
    toks = [stemmer.stem(t) for t in toks if len(t) > 1]
    return toks

def safe_cosine(a: np.ndarray, b: np.ndarray) -> float:
    if a is None or b is None:
        return 0.0
    try:
        na = np.linalg.norm(a)
        nb = np.linalg.norm(b)
    except Exception:
        return 0.0
    if na == 0 or nb == 0:
        return 0.0
    val = float(np.dot(a, b) / (na * nb))
    return max(0.0, min(1.0, val))

def compute_budget_penalty(price, budget_range, scale=0.2, cap=0.12):
    if price is None or not budget_range:
        return 0.0
    mn, mx = budget_range
    if mn is None and mx is None:
        return 0.0
    if mx is None:
        if price >= mn:
            return 0.0
        distance = mn - price
    else:
        if mn <= price <= mx:
            return 0.0
        distance = mn - price if price < mn else price - mx
    if mx is None:
        mid = max(1.0, float(mn))
    else:
        mid = max(1.0, (float(mn) + float(mx)) / 2.0)
    rel = distance / mid
    penalty = min(cap, rel * scale)
    return float(max(0.0, penalty))

def compute_forbidden_penalty_for_product(product: Dict, forbidden_tokens_set: set, per_match=FORBIDDEN_PER_MATCH, cap=FORBIDDEN_PENALTY_CAP) -> float:
    if not forbidden_tokens_set:
        return 0.0
    text_parts = []
    text_parts.append(product.get("name", ""))
    text_parts.append(product.get("description", ""))
    text_parts.append(product.get("brand", ""))
    text_parts += product.get("tags", []) if isinstance(product.get("tags", []), list) else []
    full_text = " ".join([str(x) for x in text_parts if x])
    prod_tokens = set(normalize_and_tokenize(full_text))
    matches_set = prod_tokens.intersection(forbidden_tokens_set)
    matches = len(matches_set)
    if matches <= 0:
        return 0.0
    penalty = min(cap, per_match * matches)
    return float(max(0.0, penalty))

# ---------------- تبدیل داده‌های DB به ساختار products.json-like ----------------

def build_products_from_db(user_id=USER_ID_DEFAULT) -> List[Dict]:
    products = []
    # جمع‌آوری visited items از profile
    visited = []
    favorites_ids = set()
    try:
        # try username lookup first
        profile = Profile.objects.get(user__username=user_id)
    except Profile.DoesNotExist:
        # fallback: maybe caller passed numeric user id
        try:
            profile = Profile.objects.get(user__id=int(user_id))
        except Exception:
            profile = None

    if profile:
        visited = profile.visited_items or []
        try:
            favorites_ids = set(profile.favorites.values_list('id', flat=True))
        except Exception:
            favorites_ids = set()

    # map product_id -> list[visit_time]
    visits_map = {}
    for item in visited:
        pid = item.get('product_id')
        vt = item.get('visit_time')
        if pid is None or vt is None:
            continue
        visits_map.setdefault(pid, []).append(vt)

    for p in Product.objects.all():
        # برخی فیلدها ممکن است از نوع JSONField در مدل باشند
        prod = {
            "id": getattr(p, 'external_id', None) or getattr(p, 'id'),
            "name": getattr(p, 'name', '') or '',
            "brand": getattr(p, 'brand', '') or '',
            "category": getattr(p, 'category', '') or '',
            "description": getattr(p, 'description', '') or '',
            "skin_type": getattr(p, 'skin_type', '') or '',
            "suitable_for": getattr(p, 'suitable_for', []) or [],
            "tags": getattr(p, 'tags', []) or [],
            "price": float(getattr(p, 'price', 0) or 0),
            "stock": int(getattr(p, 'stock', 0) or 0),
            "rating": float(getattr(p, 'rating', 0) or 0),
            "is_favorite": (getattr(p, 'id') in favorites_ids),
            "products_tokens": getattr(p, 'products_tokens', {}),
            "similar_products": getattr(p, 'similar_products', []),
            "similarity_threshold": getattr(p, 'similarity_threshold', SIM_THRESHOLD),
            "currency": getattr(p, 'currency', 'IRR'),
            # visit_times from profile.visited_items
            "visit_times": visits_map.get(getattr(p, 'id'), [])
        }
        # اگر favorites relation exists on Profile we can't know per-user here; keep false
        products.append(prod)
    return products

def build_purchases_from_db(user_id=USER_ID_DEFAULT) -> List[Dict]:
    recs = []
    q = OrderItem.objects.filter(order__user__username=user_id)
    for it in q.select_related('order', 'product'):
        date = getattr(it, 'date', None) or getattr(it.order, 'created_at', None)
        if date and not isinstance(date, str):
            date = date.isoformat(timespec='seconds')
        recs.append({
            "user": user_id,
            "productId": getattr(it.product, 'id'),
            "date": date,
            "quantity": int(getattr(it, 'quantity', 1) or 1)
        })
    return recs

def get_user_preferences_from_db(user_id=USER_ID_DEFAULT) -> Dict:
    try:
        profile = Profile.objects.get(user__username=user_id)
        prefs = profile.user_preferences or {}
        # keywords may be in profile.keywords
        keywords = profile.keywords or {}
        return prefs, keywords
    except Profile.DoesNotExist:
        return {}, {}

# ---------------- اصلی: محاسبه امتیاز یک محصول خاص ----------------
WEAK_WORDS = ["نباشد", "نیست", "نیابد"]

def extract_u_test_vec_from_db(keywords, user_prefs, products, vectorizer):
    u_text_parts = keywords.get("u_text_parts") or user_prefs.get("u_text_parts")
    forbidden = set(keywords.get("forbidden_ingredients", []))

    # fallback به محصولات پربازدید اگر چیزی نداشتیم
    if not u_text_parts:
        popular_products = sorted(products, key=lambda p: len(p.get("visit_times", [])), reverse=True)[:20]
        u_text_parts = [p["name"] for p in popular_products if p.get("name")]

    # حذف کلمات ضعیف
    u_text_parts = [w for w in u_text_parts if w not in WEAK_WORDS]

    # اگر چیزی داریم تبدیلش به وکتور TF-IDF
    if u_text_parts:
        u_text = " ".join(u_text_parts)
        u_test_vec = vectorizer.transform([u_text]).toarray().ravel()
    else:
        u_test_vec = np.zeros(len(vectorizer.get_feature_names_out()), dtype=float)

    return u_test_vec, forbidden

def compute_product_score(user_id: str, product_id: int) -> Optional[Dict]:
    """
    محاسبه امتیاز یک محصول خاص برای کاربر مشخص
    """
    products = build_products_from_db(user_id=user_id)
    purchases = build_purchases_from_db(user_id=user_id)
    user_prefs, keywords = get_user_preferences_from_db(user_id=user_id)
    
    # پیدا کردن محصول مورد نظر
    target_product = None
    for p in products:
        if p["id"] == product_id:
            target_product = p
            break
    
    if not target_product:
        return None

    # ساخت corpus و tfidf
    def build_product_corpus_local(products_list: List[Dict]):
        corpus = []
        ids = []
        for p in products_list:
            pid = p.get('id')
            ids.append(pid)
            # اگر products_tokens موجود باشد از آن استفاده کن
            tok_list = []
            pt = p.get('products_tokens') or {}
            if isinstance(pt, dict):
                if 'tokens' in pt and isinstance(pt['tokens'], list):
                    tok_list = pt['tokens']
                else:
                    tmp = []
                    for v in pt.values():
                        if isinstance(v, list):
                            tmp.extend(v)
                    tok_list = tmp
            elif isinstance(pt, list):
                tok_list = pt
            if not tok_list:
                pieces = []
                fields = ["name", "description", "brand", "category"]
                list_fields = ["tags", "suitable_for", "skin_type"]
                for f in fields:
                    pieces += normalize_and_tokenize(p.get(f, ""))
                for lf in list_fields:
                    for item in (p.get(lf) or []):
                        pieces += normalize_and_tokenize(item)
                tok_list = pieces
            corpus.append(" ".join(tok_list))
        return corpus, ids

    corpus, ids = build_product_corpus_local(products)
    vectorizer = TfidfVectorizer()
    X = vectorizer.fit_transform(corpus)
    id_to_idx = {pid: idx for idx, pid in enumerate(ids)}
    idx_to_id = {idx: pid for pid, idx in id_to_idx.items()}
    n = len(ids)
    sim_matrix = cosine_similarity(X, X)

    # build u_test_vec from keywords or user_prefs
    u_test_vec, forbidden_tokens_set = extract_u_test_vec_from_db(keywords, user_prefs, products, vectorizer)

    # season: choose based on current date (UTC)
    now = datetime.utcnow()
    month = now.month
    if month in (3, 4, 5):
        season_key = "spring"
    elif month in (6, 7, 8):
        season_key = "summer"
    elif month in (9, 10, 11):
        season_key = "autumn"
    else:
        season_key = "winter"
    season_kw_list = list(SeasonalKeyword.objects.filter(season=season_key).values_list('keyword', flat=True))
    s_text = " ".join(season_kw_list)
    s_season_vec = vectorizer.transform([s_text]).toarray().ravel() if s_text else np.zeros(X.shape[1], dtype=float)
    
    # visits
    W_visit = np.zeros(n, dtype=float)
    now_for_decay = datetime(2025, 8, 31, 23, 59, 59)
    
    for p in products:
        pid = p["id"]
        if pid not in id_to_idx:
            continue
        idx = id_to_idx[pid]
        visits = p.get("visit_times", []) or []
        wsum = 0.0
        for t in visits:
            dt = to_datetime(t)
            if not dt:
                continue
            delta_days = days_between(now_for_decay, dt)
            w = math.exp(-LAMBDA_V * delta_days)
            wsum += w
        W_visit[idx] = math.log(1 + wsum)
    W_visit_total = float(W_visit.sum())

    if W_visit_total > 0:
        V_user_vec = np.zeros(X.shape[1], dtype=float)
        for idx in range(n):
            if W_visit[idx] > 0:
                V_user_vec += (W_visit[idx] * X[idx].toarray().ravel())
        norm = np.linalg.norm(V_user_vec)
        if norm > 0:
            V_user_vec = V_user_vec / norm
    else:
        V_user_vec = np.zeros(X.shape[1], dtype=float)

    # ratings & favs
    pid_to_rating = {}
    for c in Comment.objects.all():
        pid = c.product_id
        pid_to_rating.setdefault(pid, []).append(c.rating)

    for pid, ratings in pid_to_rating.items():
        pid_to_rating[pid] = sum(ratings) / len(ratings)  # میانگین

    r_norm = np.zeros(n, dtype=float)
    fav_flags = np.zeros(n, dtype=int)
    total_user_favs = 0
    for p in products:
        if p['id'] not in id_to_idx:
            continue
        idx = id_to_idx[p['id']]
        rating = pid_to_rating.get(p['id'], 0.0)
        r_norm[idx] = max(0.0, min(1.0, (float(rating) - 1.0) / 4.0))
        if p.get('is_favorite'):
            fav_flags[idx] = 1
            total_user_favs += 1

    # purchases weights
    W_buy = np.zeros(n, dtype=float)
    for rec in purchases:
        if rec.get('user') != user_id:
            continue
        pid = rec.get('productId')
        if pid not in id_to_idx:
            continue
        date = rec.get('date')
        qty = rec.get('quantity', 1) or 1
        dt = to_datetime(date)
        if not dt:
            continue
        delta_days = days_between(now_for_decay, dt)
        w = qty * math.exp(-LAMBDA_BUY * delta_days)
        W_buy[id_to_idx[pid]] += w
    W_buy_total = float(W_buy.sum())

    # budget
    budget_choice = user_prefs.get('budget', None) if user_prefs else None
    brand_pref = user_prefs.get('brand_preference', None) if user_prefs else None
    only_in_stock = user_prefs.get('only_in_stock', False) if user_prefs else False

    budget_ranges = {
        "زیر 200 هزار تومان": (0, 200_000),
        "200 تا 400 هزار تومان": (200_000, 400_000),
        "400 تا 700 هزار تومان": (400_000, 700_000),
        "700 هزار تا 1 میلیون تومان": (700_000, 1_000_000),
        "بالاتر از 1 میلیون تومان": (1_000_000, None)
    }
    budget_range_for_scoring = None
    if isinstance(budget_choice, dict):
        budget_range_for_scoring = (budget_choice.get('min'), budget_choice.get('max'))
    elif isinstance(budget_choice, str):
        budget_range_for_scoring = budget_ranges.get(budget_choice)
    elif isinstance(budget_choice, int):
        keys = list(budget_ranges.keys())
        if 0 <= (budget_choice - 1) < len(keys):
            budget_range_for_scoring = budget_ranges[keys[budget_choice - 1]]

    product_map = {p["id"]: p for p in products}

    # محاسبه امتیاز برای محصول مورد نظر
    if target_product["id"] not in id_to_idx:
        return None
        
    idx = id_to_idx[target_product["id"]]
    pid = idx_to_id[idx]
    p = product_map.get(pid)
    if not p:
        return None
        
    v_p = X[idx].toarray().ravel()
    sims = sim_matrix[idx]
    q_idx = [j for j in range(n) if sims[j] >= SIM_THRESHOLD]
    if idx not in q_idx:
        q_idx.append(idx)
        
    T_p = safe_cosine(u_test_vec, v_p)
    S_p = safe_cosine(s_season_vec, v_p)
    V_sim_p = safe_cosine(V_user_vec, v_p) if np.linalg.norm(V_user_vec) > 0 else 0.0
    
    if W_visit_total > 0:
        numerator = sum(W_visit[q] for q in q_idx)
        ratio_visit_p = numerator / (W_visit_total + KAPPA)
    else:
        ratio_visit_p = 0.0
        
    denom_R = sum(sim_matrix[idx][q] for q in q_idx)
    if denom_R > 0:
        R_Q_p = sum(sim_matrix[idx][q] * r_norm[q] for q in q_idx) / denom_R
    else:
        R_Q_p = 0.0
                
    count_fav_in_Q = sum(int(fav_flags[q]) for q in q_idx)
    ratio_fav_p = (count_fav_in_Q / (total_user_favs + KAPPA)) if total_user_favs > 0 else 0.0
    ratio_buy_p = (sum(W_buy[q] for q in q_idx) / (W_buy_total + KAPPA)) if W_buy_total > 0 else 0.0
    
    score_base = (W_T * T_p + W_S * S_p + W_VSIM * V_sim_p + W_VRATIO * ratio_visit_p + W_R * R_Q_p)
    score_prime = score_base * (1.0 + BETA_FAV * ratio_fav_p) * (1.0 + BETA_BUY * ratio_buy_p)
    
    budget_penalty = 0.0
    if budget_range_for_scoring:
        price = p.get('price', None)
        budget_penalty = compute_budget_penalty(price, budget_range_for_scoring, scale=0.2, cap=0.12)
        score_prime = score_prime * (1.0 - budget_penalty)
        
    forbidden_penalty = compute_forbidden_penalty_for_product(p, forbidden_tokens_set, per_match=FORBIDDEN_PER_MATCH, cap=FORBIDDEN_PENALTY_CAP)
    score_prime = score_prime * (1.0 - forbidden_penalty)
    
    final_score = max(0.0, min(1.0, score_prime))

    return {
        "product_id": pid,
        "name": p.get('name'),
        "brand": p.get('brand'),
        "category": p.get('category'),
        "price": p.get('price'),
        "currency": p.get('currency'),
        "final_score": final_score,
        "details": {
            "T": T_p,
            "S": S_p,
            "V_sim": V_sim_p,
            "ratio_visit": ratio_visit_p,
            "R_Q": R_Q_p,
            "ratio_fav": ratio_fav_p,
            "ratio_buy": ratio_buy_p,
            "budget_penalty": budget_penalty,
            "forbidden_penalty": forbidden_penalty
        }
    }