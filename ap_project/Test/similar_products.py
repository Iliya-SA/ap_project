# -*- coding: utf-8 -*-
"""
find_similar_with_hazm.py
- از Hazm برای نرمال‌سازی و توکنایز استفاده می‌کند
- سپس TF-IDF و شباهت کسینوسی را محاسبه می‌کند
- خروجی: similar_products.json (شامل توکن‌ها و مشابه‌ها)
"""

import json, os, re
from datetime import datetime
from typing import List, Dict
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# Hazm
from hazm import Normalizer, word_tokenize, Stemmer

BASE_DIR = os.path.dirname(os.path.abspath(__file__))  # مسیر پوشه فعلی اسکریپت
INPUT_PATH = os.path.join(BASE_DIR, "products.json")
OUTPUT_PATH = os.path.join(BASE_DIR, "similar_products.json")
SIM_THRESHOLD = 0.4

# ---------- Hazm setup ----------
normalizer = Normalizer()
stemmer = Stemmer()

# ---------- نرمال‌سازی با Hazm ----------
def normalize_persian_hazm(text: str) -> str:
    if not text:
        return ""
    s = str(text)
    s = normalizer.normalize(s)   # حذف فاصله‌های اضافی، تبدیل ي->ی و ... (Hazm)
    # در صورت نیاز می‌توانیم نگارشی اضافی را حذف کنیم:
    s = re.sub(r"[^\w\s\u0600-\u06FF]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s

# ---------- توکنایز با Hazm + (اختیاری) استمینگ ----------
def tokenize_hazm(text: str, do_stem: bool = True) -> List[str]:
    s = normalize_persian_hazm(text)
    if not s:
        return []
    toks = word_tokenize(s)  # توکنایزر لغت Hazm
    if do_stem:
        toks = [stemmer.stem(t) for t in toks if t.strip() != ""]
    # حذف توکن‌های خیلی کوتاه یا stopwords در صورت نیاز می‌تواند اینجا انجام شود
    return toks

# ---------- بارگذاری ----------
def load_products(path: str) -> List[Dict]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    products = data.get("products", data if isinstance(data, list) else [])
    return products

# ---------- ساخت کورپوس و نگهداری توکن‌ها ----------
def build_corpus_and_tokens(products: List[Dict]) -> (List[str], Dict[int, Dict]):
    corpus = []
    tokens_map = {}
    for p in products:
        pid = p.get("id")
        prop_tokens = {}
        pieces = []
        # فیلدهای متنی
        fields = ["name", "description", "brand", "category"]
        list_fields = ["skin_type", "suitable_for", "tags"]
        for f in fields:
            txt = p.get(f, "") or ""
            tks = tokenize_hazm(txt, do_stem=True)
            prop_tokens[f] = tks
            pieces.extend(tks)
        for lf in list_fields:
            val = p.get(lf, []) or []
            lf_tokens = []
            for item in val:
                lf_tokens += tokenize_hazm(item, do_stem=True)
            prop_tokens[lf] = lf_tokens
            pieces.extend(lf_tokens)

        # --- اینجا توکن‌های جامع (برای ریکامندیشن) را اضافه می‌کنیم ---
        combined_tokens = list(dict.fromkeys(pieces))  # حفظ ترتیب و حذف تکرار
        prop_tokens["tokens"] = combined_tokens
        # corpus از همین توکن‌های ترکیبی ساخته می‌شود
        corpus.append(" ".join(combined_tokens))
        tokens_map[pid] = prop_tokens

    return corpus, tokens_map

# ---------- TF-IDF و شباهت ----------
def compute_similarity(corpus: List[str]):
    vectorizer = TfidfVectorizer()
    X = vectorizer.fit_transform(corpus)
    sim_matrix = cosine_similarity(X, X)
    return sim_matrix

def find_similars(products: List[Dict], sim_matrix: np.ndarray, threshold: float):
    idx_to_id = [p.get("id") for p in products]
    n = len(products)
    result = {}
    for i in range(n):
        pid = idx_to_id[i]
        sims = sim_matrix[i]
        similar_ids = [idx_to_id[j] for j in range(n) if j != i and sims[j] >= threshold]
        result[pid] = sorted(similar_ids, reverse=True)  # id بیشتر -> id کمتر
    return result

def save_output(output_path: str, tokens_map: Dict[int, Dict], similar_map: Dict[int, List[int]]):
    out = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "products_tokens": tokens_map,
        "similar_products": similar_map,
        "similarity_threshold": SIM_THRESHOLD
    }
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print("Saved:", output_path)

def main():
    if not os.path.exists(INPUT_PATH):
        raise FileNotFoundError(f"Input file not found: {INPUT_PATH}")
    products = load_products(INPUT_PATH)
    print("Loaded products:", len(products))
    corpus, tokens_map = build_corpus_and_tokens(products)
    sim_matrix = compute_similarity(corpus)
    similar_map = find_similars(products, sim_matrix, SIM_THRESHOLD)
    save_output(OUTPUT_PATH, tokens_map, similar_map)
    total_pairs = sum(len(v) for v in similar_map.values())
    print(f"Total similar links (>= {SIM_THRESHOLD}): {total_pairs}")

if __name__ == "__main__":
    main()
