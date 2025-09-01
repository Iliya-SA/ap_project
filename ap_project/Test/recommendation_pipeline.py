# -*- coding: utf-8 -*-
"""
recommendation_pipeline_full.py
- ایجاد purchases.json (ساختگی) اگر وجود نداشته باشد
- ایجاد seasonal_vectors.json (بر اساس محصولات) اگر وجود نداشته باشد
- ساخت TF-IDF برای محصولات، محاسبه شباهت‌ها
- محاسبه امتیاز هر محصول برای کاربر 'u1' بر اساس فرمول‌های داده‌شده
- خروجی: recommendations_user_u1.json (مرتب بر اساس final_score)
"""

import os
import json
import math
import random
from datetime import datetime, timedelta
from typing import List, Dict, Tuple
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# Hazm
from hazm import Normalizer, word_tokenize, Stemmer

# ---------------- تنظیمات و پارامترها ----------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))  # مسیر پوشه فعلی اسکریپت
INPUT_PATH = os.path.join(BASE_DIR, "products.json")

PRODUCTS_PATH = os.path.join(BASE_DIR, "products.json")
PURCHASES_PATH = os.path.join(BASE_DIR, "purchases.json")
SEASON_PATH = os.path.join(BASE_DIR, "seasonal_vectors.json")
USER_PREFS_PATH = os.path.join(BASE_DIR, "user_preferences.json")
KEYWORDS_PATH = os.path.join(BASE_DIR, "keywords.json")
OUTPUT_RECS = os.path.join(BASE_DIR, "recommendations_user_u1.json")

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

# forbidden penalty defaults
FORBIDDEN_PENALTY_CAP = 0.25   # حداکثر کاهش امتیاز (25%)
FORBIDDEN_PER_MATCH = 0.06     # برای هر تطابقِ متمایز چقدر کم شود (تا cap)


USER_ID = "u1"   # user id برای مثال

random.seed(12345)  # reproducible synthetic data

normalizer = Normalizer()
stemmer = Stemmer()


# ---------------- کمک‌تابع‌ها ----------------
def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def save_json(obj, path):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)

def to_datetime(tstr):
    # قبول ISO format
    try:
        return datetime.fromisoformat(tstr)
    except Exception:
        for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
            try:
                return datetime.strptime(tstr, fmt)
            except Exception:
                continue
    raise ValueError("Unknown date format: " + str(tstr))

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
    na = np.linalg.norm(a)
    nb = np.linalg.norm(b)
    if na == 0 or nb == 0:
        return 0.0
    val = float(np.dot(a, b) / (na * nb))
    return max(0.0, min(1.0, val))


# ---------------- ساخت فایل purchases.json (ساختگی) ----------------
def build_synthetic_purchases(products: List[Dict], user_id=USER_ID, out_path=PURCHASES_PATH):
    # اگر فایل وجود داشته باشد کاری نکن
    if os.path.exists(out_path):
        print("Purchases file exists ->", out_path)
        return
    now = datetime(2025, 8, 31, 23, 59, 59)  # consistent with dataset
    product_ids = [p["id"] for p in products]
    purchases = []
    # انتخاب تصادفی 12-20 محصول برای خرید نمونه
    num_buy_items = min(20, max(8, len(product_ids)//6))
    chosen = random.sample(product_ids, num_buy_items)
    for pid in chosen:
        # تعداد خرید بین 1 تا 4
        qty = random.randint(1, 3)
        # تاریخ خرید یک تا چند بار در بازه Jan 1 2025 .. Aug 31 2025
        num_records = random.randint(1, 3)
        for _ in range(num_records):
            days_ago = random.randint(0, (now - datetime(2025,1,1)).days)
            date = now - timedelta(days=days_ago, hours=random.randint(0,23), minutes=random.randint(0,59))
            purchases.append({
                "user": user_id,
                "productId": pid,
                "date": date.isoformat(timespec='seconds'),
                "quantity": qty
            })
    save_json(purchases, out_path)
    print("Synthetic purchases written to", out_path, "records:", len(purchases))

# ---------------- ساخت seasonal_vectors.json ----------------
def build_seasonal_vectors(products: List[Dict], out_path=SEASON_PATH):
    if os.path.exists(out_path):
        print("Seasonal vectors file exists ->", out_path)
        return
    # جمع‌آوری کلمات پر تکرار از فیلدها برای هر دسته تا کلیدواژه فصل بسازیم
    # اما ساده‌تر: برای هر فصل مجموعه‌ای از کلمات کلیدی مناسب تعیین می‌کنیم
    seasonal = {
        "spring": ["سبک", "جذب سریع", "روشن‌کننده", "لایه‌بردار", "آنتی‌اکسیدان", "ویتامین C"],
        "summer": ["ضد آفتاب", "جذب سریع", "سبک", "مات‌کننده", "بدون الکل", "محافظت"],
        "autumn": ["مرطوب‌کننده", "تغذیه‌کننده", "بازسازی", "ضدچروک", "آبرسان", "پپتید"],
        "winter": ["تغذیه‌کننده", "مغذی", "شب", "روغن", "محافظ", "آبرسان"]
    }
    # ذخیره به صورت JSON
    save_json(seasonal, out_path)
    print("Seasonal vectors written to", out_path)

# ---------------- ساخت کورپوس محصولات و TF-IDF ----------------
def build_product_corpus(products: List[Dict]) -> Tuple[List[str], List[int]]:
    """
    اگر فایل similar_products.json وجود داشته باشد:
      - از products_tokens[pid]["tokens"] استفاده می‌کند (فوق‌العاده سریع)
    وگرنه:
      - مثل قبل متن را normalize_and_tokenize می‌کند.
    """
    corpus = []
    ids = []

    sim_path = "similar_products.json"
    tokens_map_from_sim = {}

    if os.path.exists(sim_path):
        try:
            sim_json = load_json(sim_path)
            tokens_map_from_sim = sim_json.get("products_tokens", {})
        except Exception:
            tokens_map_from_sim = {}

    for p in products:
        pid = p.get("id")
        ids.append(pid)
        # تلاش برای گرفتن توکن از فایل similar (کلید‌ها ممکنه str باشند)
        tok_list = []
        if tokens_map_from_sim:
            entry = None
            if str(pid) in tokens_map_from_sim:
                entry = tokens_map_from_sim[str(pid)]
            elif pid in tokens_map_from_sim:
                entry = tokens_map_from_sim[pid]
            # entry ممکن است dict per-field یا list باشد
            if entry:
                if isinstance(entry, dict):
                    # اگر کلید tokens وجود داشت، دقیقا از آن استفاده کن
                    if "tokens" in entry and isinstance(entry["tokens"], list):
                        tok_list = entry["tokens"]
                    else:
                        # جمع کردن تمام توکن‌های فیلدها (fallback)
                        tmp = []
                        for v in entry.values():
                            if isinstance(v, list):
                                tmp.extend(v)
                        tok_list = tmp
                elif isinstance(entry, list):
                    tok_list = entry

        # fallback اگر توکن از فایل similar پیدا نشد
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

#--------------------------------


def compute_budget_penalty(price, budget_range, scale=0.2, cap=0.12):
    """
    محاسبه‌ی جریمه بودجه بین 0 و cap.
    - price: عدد قیمت محصول (مثلاً تومان) یا None
    - budget_range: tuple (min, max) ؛ max می‌تواند None باشد (یعنی سقف ندارد)
    - scale: حساسیت کلی (بیشتر => جریمه زودتر بالا می‌رود)
    - cap: بیشینه‌ی جریمه (مثلاً 0.12 یعنی حداکثر 12% کاهش در امتیاز)
    خروجی: عدد اعشاری بین 0.0 و cap
    """
    if price is None or not budget_range:
        return 0.0
    mn, mx = budget_range
    # اگر محدوده مشخص نباشد چیزی اعمال نمی‌شود
    if mn is None and mx is None:
        return 0.0
    # داخل محدوده => بدون جریمه
    if mx is None:
        if price >= mn:
            return 0.0
        distance = mn - price
    else:
        if mn <= price <= mx:
            return 0.0
        distance = mn - price if price < mn else price - mx
    # برای نرمال‌سازی نسبت به مقیاس بودجه از میانه استفاده می‌کنیم
    if mx is None:
        mid = max(1.0, float(mn))
    else:
        mid = max(1.0, (float(mn) + float(mx)) / 2.0)
    rel = distance / mid  # نسبت فاصله به میانه‌ی بازه
    penalty = min(cap, rel * scale)
    return float(max(0.0, penalty))

def compute_forbidden_penalty_for_product(product: Dict, forbidden_tokens_set: set, per_match=FORBIDDEN_PER_MATCH, cap=FORBIDDEN_PENALTY_CAP) -> float:
    """
    بررسی می‌کند چند کلمه/توکن از forbidden_tokens_set در متن محصول وجود دارد.
    جریمه = min(cap, per_match * matches)
    forbidden_tokens_set باید توکنایز شده و stem شده (همین تابع فرض را دارد).
    """
    if not forbidden_tokens_set:
        return 0.0
    # جمع‌آوری توکن‌های متن محصول (name, description, tags, brand)
    text_parts = []
    text_parts.append(product.get("name", ""))
    text_parts.append(product.get("description", ""))
    text_parts.append(product.get("brand", ""))
    text_parts += product.get("tags", []) if isinstance(product.get("tags", []), list) else []
    full_text = " ".join([str(x) for x in text_parts if x])
    prod_tokens = set(normalize_and_tokenize(full_text))
    # تعداد تطابق توکن‌های ممنوعه
    matches_set = prod_tokens.intersection(forbidden_tokens_set)
    matches = len(matches_set)
    if matches <= 0:
        return 0.0
    penalty = min(cap, per_match * matches)
    return float(max(0.0, penalty))

# ---------------- main pipeline ----------------
def main():
    # 1) بارگذاری محصولات
    if not os.path.exists(PRODUCTS_PATH):
        raise FileNotFoundError(f"products.json not found in working dir.")
    products_data = load_json(PRODUCTS_PATH)
    products = products_data.get("products", products_data if isinstance(products_data, list) else [])
    print("Loaded products:", len(products))

    # 2) تولید purchases.json و seasonal_vectors.json در صورت نبود
    build_synthetic_purchases(products)
    build_seasonal_vectors(products)

    # 3) بارگذاری purchases و seasonal vectors
    purchases = load_json(PURCHASES_PATH) if os.path.exists(PURCHASES_PATH) else []
    seasonal = load_json(SEASON_PATH) if os.path.exists(SEASON_PATH) else {}

    # 4) بردارسازی TF-IDF برای محصولات
    corpus, ids = build_product_corpus(products)
    vectorizer = TfidfVectorizer()
    X = vectorizer.fit_transform(corpus)   # (n_products, n_features)
    id_to_idx = {pid: idx for idx, pid in enumerate(ids)}
    idx_to_id = {idx: pid for pid, idx in id_to_idx.items()}
    n = len(ids)
    print("TF-IDF matrix shape:", X.shape)

    # 5) محاسبه ماتریس شباهت کسینوسی
    sim_matrix = cosine_similarity(X, X)

    # 6) ساخت بردار u_test از keywords.json یا user_preferences.json
    u_text_parts = []
    forbidden_tokens_set = set()   # ← forbidden tokens will be stored here (توکنایز و stem شده)
    if os.path.exists(KEYWORDS_PATH):
        kw = load_json(KEYWORDS_PATH)
        # kw ممکن است dict از فیلدها -> لیست/رشته
        # IMPORTANT: do NOT add forbidden_ingredients into u_text_parts
        for k, v in kw.items():
            if k == "forbidden_ingredients":
                # توکنایز و نرمال‌سازی forbidden keywords و ذخیره جدا
                # ممکن است v یک لیست از عبارات باشد
                toks = []
                if isinstance(v, list):
                    for item in v:
                        toks += normalize_and_tokenize(str(item))
                elif isinstance(v, str):
                    toks += normalize_and_tokenize(v)
                # حذف کلمات ضعیف مثل 'نباشد' که معنی ندارد
                toks = [t for t in toks if t not in ("نباشد", "نیست", "نیابد")]
                forbidden_tokens_set = set(toks)
                continue
            # بقیهٔ کلیدواژه‌ها را وارد u_text_parts می‌کنیم
            if isinstance(v, list):
                u_text_parts += [str(x) for x in v]
            elif isinstance(v, str):
                u_text_parts.append(v)
    if not u_text_parts and os.path.exists(USER_PREFS_PATH):
        up = load_json(USER_PREFS_PATH)
        for v in up.values():
            if isinstance(v, list):
                u_text_parts += [str(x) for x in v]
            elif isinstance(v, str):
                u_text_parts.append(v)
    # fallback: از نام‌ محصولات پربازدید کاربر (visit_times) تولید کن
    if not u_text_parts:
        # انتخاب 5 محصول با بیشترین visit_times
        products_sorted_by_visits = sorted(products, key=lambda p: len(p.get("visit_times",[])), reverse=True)
        for p in products_sorted_by_visits[:6]:
            u_text_parts.append(p.get("name",""))
            u_text_parts.append(" ".join(p.get("tags",[])))
    u_text = " ".join(u_text_parts)
    if u_text.strip():
        u_test_vec = vectorizer.transform([u_text]).toarray().ravel()
    else:
        u_test_vec = np.zeros(X.shape[1], dtype=float)

    # 7) انتخاب فصل بر اساس تاریخ فعلی (utc date -> use 2025-09-01 if now)
    # تعیین فصل ساده (spring=3-5, summer=6-8, autumn=9-11, winter=12,1,2)
    now = datetime.utcnow()
    month = now.month
    if month in (3,4,5):
        season_key = "spring"
    elif month in (6,7,8):
        season_key = "summer"
    elif month in (9,10,11):
        season_key = "autumn"
    else:
        season_key = "winter"
    season_kw_list = seasonal.get(season_key, [])
    s_text = " ".join(season_kw_list)
    s_season_vec = vectorizer.transform([s_text]).toarray().ravel() if s_text else np.zeros(X.shape[1], dtype=float)
    print("Using season:", season_key, "keywords:", season_kw_list)

    # 8) Visits: جمع‌آوری بازدیدها از محصولات برای user_id (در این dataset هر visit_times متعلق به user نمونه)
    # فرض: visit_times در products مربوط به همین user هستند
    W_visit = np.zeros(n, dtype=float)
    now_for_decay = datetime(2025,8,31,23,59,59)  # همگام با دیتاست
    for p in products:
        pid = p["id"]
        idx = id_to_idx[pid]
        visits = p.get("visit_times", []) or []
        wsum = 0.0
        for t in visits:
            try:
                dt = to_datetime(t)
            except Exception:
                continue
            delta_days = days_between(now_for_decay, dt)
            w = math.exp(-LAMBDA_V * delta_days)
            wsum += w
        # optional compression
        W_visit[idx] = math.log(1 + wsum)
    W_visit_total = float(W_visit.sum())

    # 9) V_user vector
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

    # 10) Ratings, favorites, purchases -> پیش‌محاسبه
    r_norm = np.zeros(n, dtype=float)
    fav_flags = np.zeros(n, dtype=int)
    total_user_favs = 0
    for p in products:
        idx = id_to_idx[p["id"]]
        rating = p.get("rating", 0.0)
        r_norm[idx] = max(0.0, min(1.0, (rating - 1.0) / 4.0))
        if p.get("is_favorite"):
            fav_flags[idx] = 1
            total_user_favs += 1

    # purchases: از purchases.json خوانده شده است
    W_buy = np.zeros(n, dtype=float)
    # purchases list of dict {user, productId, date, quantity}
    for rec in purchases:
        if rec.get("user") != USER_ID:
            continue
        pid = rec.get("productId")
        if pid not in id_to_idx:
            continue
        date = rec.get("date")
        qty = rec.get("quantity", 1)
        try:
            dt = to_datetime(date)
        except Exception:
            continue
        delta_days = days_between(now_for_decay, dt)
        w = qty * math.exp(-LAMBDA_BUY * delta_days)
        W_buy[id_to_idx[pid]] += w
    W_buy_total = float(W_buy.sum())

    # 11) تاثیر دادن بودجه در امتیاز
    user_prefs = {}
    if os.path.exists(USER_PREFS_PATH):
        try:
            user_prefs = load_json(USER_PREFS_PATH)
        except Exception:
            user_prefs = {}

    budget_choice = user_prefs.get("budget", None)
    brand_pref = user_prefs.get("brand_preference", None)
    only_in_stock = user_prefs.get("only_in_stock", False)
    budget_strict = user_prefs.get("budget_strict", False)  # اگر کاربر خواست حذف سخت

    # map textual budgets to ranges (تومان)
    budget_ranges = {
        "زیر 200 هزار تومان": (0, 200_000),
        "200 تا 400 هزار تومان": (200_000, 400_000),
        "400 تا 700 هزار تومان": (400_000, 700_000),
        "700 هزار تا 1 میلیون تومان": (700_000, 1_000_000),
        "بالاتر از 1 میلیون تومان": (1_000_000, None)  # None یعنی سقف ندارد
    }

    # تبدیل budget_choice به بازه عددی برای scoring
    budget_range_for_scoring = None
    if isinstance(budget_choice, dict):
        budget_range_for_scoring = (budget_choice.get("min"), budget_choice.get("max"))
    elif isinstance(budget_choice, str):
        budget_range_for_scoring = budget_ranges.get(budget_choice)
    elif isinstance(budget_choice, int):
        keys = list(budget_ranges.keys())
        if 0 <= (budget_choice - 1) < len(keys):
            budget_range_for_scoring = budget_ranges[keys[budget_choice - 1]]

    # 12) برای هر محصول p محاسبات ...
    results = []
    for idx in range(n):
        pid = idx_to_id[idx]
        p = products[id_to_idx[pid]]   # <-- اضافه شد (مهم)
        v_p = X[idx].toarray().ravel()
        # Q(p): هم خودش و هم محصولات مشابه با sim >= SIM_THRESHOLD
        sims = sim_matrix[idx]
        q_idx = [j for j in range(n) if sims[j] >= SIM_THRESHOLD]
        if idx not in q_idx:
            q_idx.append(idx)
        # T and S
        T_p = safe_cosine(u_test_vec, v_p)
        S_p = safe_cosine(s_season_vec, v_p)
        # V_sim
        V_sim_p = safe_cosine(V_user_vec, v_p) if np.linalg.norm(V_user_vec) > 0 else 0.0
        # ratio_visit
        if W_visit_total > 0:
            numerator = sum(W_visit[q] for q in q_idx)
            ratio_visit_p = numerator / (W_visit_total + KAPPA)
        else:
            ratio_visit_p = 0.0
        # R_Q(p)
        denom_R = sum(sim_matrix[idx][q] for q in q_idx)
        if denom_R > 0:
            R_Q_p = sum(sim_matrix[idx][q] * r_norm[q] for q in q_idx) / denom_R
        else:
            R_Q_p = 0.0
        # ratio_fav
        count_fav_in_Q = sum(int(fav_flags[q]) for q in q_idx)
        ratio_fav_p = (count_fav_in_Q / (total_user_favs + KAPPA)) if total_user_favs > 0 else 0.0
        # ratio_buy
        ratio_buy_p = (sum(W_buy[q] for q in q_idx) / (W_buy_total + KAPPA)) if W_buy_total > 0 else 0.0
        # Score base
        score_base = (W_T * T_p + W_S * S_p + W_VSIM * V_sim_p + W_VRATIO * ratio_visit_p + W_R * R_Q_p)
        # Apply boosts
        score_prime = score_base * (1.0 + BETA_FAV * ratio_fav_p) * (1.0 + BETA_BUY * ratio_buy_p)

        # ---------- budget penalty (soft) ----------
        budget_penalty = 0.0
        if budget_range_for_scoring:
            price = p.get("price", None)
            budget_penalty = compute_budget_penalty(price, budget_range_for_scoring, scale=0.2, cap=0.12)
            score_prime = score_prime * (1.0 - budget_penalty)

        # ---------- forbidden penalty (soft multiplicative at the end) ----------
        forbidden_penalty = compute_forbidden_penalty_for_product(p, forbidden_tokens_set, per_match=FORBIDDEN_PER_MATCH, cap=FORBIDDEN_PENALTY_CAP)
        score_prime = score_prime * (1.0 - forbidden_penalty)

        final_score = max(0.0, min(1.0, score_prime))
        results.append({
            "product_id": pid,
            "index": idx,
            "T": T_p,
            "S": S_p,
            "V_sim": V_sim_p,
            "ratio_visit": ratio_visit_p,
            "R_Q": R_Q_p,
            "ratio_fav": ratio_fav_p,
            "ratio_buy": ratio_buy_p,
            "score_base": score_base,
            "budget_penalty": budget_penalty,
            "forbidden_penalty": forbidden_penalty,
            "final_score": final_score
        })

    # 13) فیلترهای سخت از user_preferences (اگر موجود باشند) — اینجا ساده عمل می‌کنیم

    user_prefs = {}
    if os.path.exists(USER_PREFS_PATH):
        try:
            user_prefs = load_json(USER_PREFS_PATH)
        except Exception:
            user_prefs = {}
            
    brand_pref = user_prefs.get("brand_preference", None)
    only_in_stock = user_prefs.get("only_in_stock", False)
    
    # apply filters (hard)
    filtered = []
    for r in results:
        pid = r["product_id"]
        p = products[id_to_idx[pid]]
        price = p.get("price", None)

        # brand filter
        if brand_pref and isinstance(brand_pref, str) and brand_pref != "برند مهم نیست":
            if p.get("brand") != brand_pref:
                continue
        # stock filter
        if only_in_stock and p.get("stock", 0) <= 0:
            continue
        filtered.append(r)
    if not filtered:
        filtered = results

    # 14) مرتب‌سازی بر اساس final_score نزولی و ساخت خروجی نهایی
    filtered.sort(key=lambda x: x["final_score"], reverse=True)
    out_list = []
    for r in filtered:
        pid = r["product_id"]
        p = products[id_to_idx[pid]]
        out_list.append({
            "product_id": pid,
            "name": p.get("name"),
            "brand": p.get("brand"),
            "category": p.get("category"),
            "price": p.get("price"),
            "currency": p.get("currency"),
            "final_score": r["final_score"],
            "details": {
                "T": r["T"],
                "S": r["S"],
                "V_sim": r["V_sim"],
                "ratio_visit": r["ratio_visit"],
                "R_Q": r["R_Q"],
                "ratio_fav": r["ratio_fav"],
                "ratio_buy": r["ratio_buy"],
                "budget_penalty": r.get("budget_penalty", 0.0),
                "forbidden_penalty": r.get("forbidden_penalty", 0.0)            }
        })

    output = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "user": USER_ID,
        "params": {
            "SIM_THRESHOLD": SIM_THRESHOLD,
            "KAPPA": KAPPA,
            "HALF_LIFE_VISITS": HALF_LIFE_VISITS,
            "HALF_LIFE_BUY": HALF_LIFE_BUY,
            "weights": {"W_T": W_T, "W_S": W_S, "W_VSIM": W_VSIM, "W_VRATIO": W_VRATIO, "W_R": W_R},
            "boosts": {"BETA_FAV": BETA_FAV, "BETA_BUY": BETA_BUY},
            "season_used": season_key,
            "season_keywords": season_kw_list,
            "forbidden_penalty_cap": FORBIDDEN_PENALTY_CAP,
            "forbidden_per_match": FORBIDDEN_PER_MATCH},
            "recommendations": out_list
    }
    save_json(output, OUTPUT_RECS)
    print("Saved recommendations to", OUTPUT_RECS)
    print("Top 10 recommendations (product_id, name, score):")
    for it in out_list[:10]:
        print(it["product_id"], it["name"], round(it["final_score"], 4))


if __name__ == "__main__":
    main()
