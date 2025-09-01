"""
{
  "action": "new",
  "product": {
    "name": "کرم تست آبرسان",
    "brand": "تست برند",
    "category": "مرطوب کننده",
    "description": "این یک محصول تستی برای بررسی افزودن محصول جدید است.",
    "skin_type": ["خشک"],
    "suitable_for": ["چروک و خطوط ریز"],
    "tags": ["حاوی ویتامین C"],
    "price": 123456,
    "stock": 50
  }
}

{
  "action": "edit",
  "product": {
    "id": 1,
    "name": "کرم تست آبرسان (ویرایش)",
    "brand": "تست برند ویرایش شده",
    "category": "مرطوب کننده",
    "description": "این محصول تستی ویرایش شده است.",
    "skin_type": ["نرمال"],
    "suitable_for": ["قرمزی و التهاب"],
    "tags": ["فاقد پارابن"],
    "price": 654321,
    "stock": 100
  }
}

cd ap_project
python manage.py update_product_and_similarity

"""

from django.core.management.base import BaseCommand
import json, os, re
from hazm import Normalizer, word_tokenize, Stemmer
from django.db import transaction
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))  # مسیر پوشه فعلی اسکریپت
INPUT_PATH = os.path.join(BASE_DIR, "new_or_edit_product.json")

SIM_THRESHOLD = 0.4

normalizer = Normalizer()
stemmer = Stemmer()

def normalize_persian_hazm(text):
    if not text:
        return ""
    s = str(text)
    s = normalizer.normalize(s)
    s = re.sub(r"[^\w\s\u0600-\u06FF]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s

def tokenize_hazm(text, do_stem=True):
    s = normalize_persian_hazm(text)
    if not s:
        return []
    toks = word_tokenize(s)
    if do_stem:
        toks = [stemmer.stem(t) for t in toks if t.strip() != ""]
    return toks

def build_tokens_from_payload(product_dict):
    """مثل اسکریپت آفلاین: خروجی dict prop_tokens و string مرکب"""
    prop_tokens = {}
    pieces = []
    fields = ["name", "description", "brand", "category"]
    list_fields = ["skin_type", "suitable_for", "tags"]
    for f in fields:
        txt = product_dict.get(f, "") or ""
        tks = tokenize_hazm(txt, do_stem=True)
        prop_tokens[f] = tks
        pieces.extend(tks)
    for lf in list_fields:
        val = product_dict.get(lf, []) or []
        lf_tokens = []
        for item in val:
            lf_tokens += tokenize_hazm(item, do_stem=True)
        prop_tokens[lf] = lf_tokens
        pieces.extend(lf_tokens)
    combined_tokens = list(dict.fromkeys(pieces))
    prop_tokens["tokens"] = combined_tokens
    return prop_tokens, " ".join(combined_tokens)

def build_tokens_from_model_obj(p):
    """
    اگر محصول در DB توکن ذخیره‌شده داره ازش استفاده کن،
    وگرنه از فیلدهای محصول توکن‌سازی کن.
    خروجی: لیست توکن‌ها (tokens) و رشتهٔ مرکب
    """
    # تلاش برای خواندن products_tokens از مدل
    val = getattr(p, "products_tokens", None)
    if val:
        # اگر dict و key tokens
        if isinstance(val, dict) and "tokens" in val:
            tokens = val.get("tokens") or []
            if isinstance(tokens, list):
                return tokens, " ".join(tokens)
        # اگر لیست
        if isinstance(val, list):
            return val, " ".join(val)
        # اگر string حاوی JSON
        if isinstance(val, str):
            try:
                parsed = json.loads(val)
                if isinstance(parsed, dict) and "tokens" in parsed and isinstance(parsed["tokens"], list):
                    return parsed["tokens"], " ".join(parsed["tokens"])
                if isinstance(parsed, list):
                    return parsed, " ".join(parsed)
            except Exception:
                pass
    # fallback: بساز از فیلدهای مدل (مطابق build_tokens_from_payload)
    payload = {
        "name": getattr(p, "name", "") or "",
        "description": getattr(p, "description", "") or "",
        "brand": getattr(p, "brand", "") or "",
        "category": getattr(p, "category", "") or "",
        "skin_type": getattr(p, "skin_type", []) or [],
        "suitable_for": getattr(p, "suitable_for", []) or [],
        "tags": getattr(p, "tags", []) or [],
    }
    tok_dict, vec = build_tokens_from_payload(payload)
    return tok_dict.get("tokens", []), vec

def compute_similarities_for_corpus(corpus):
    """
    corpus: list[str] (هر عضو یک سندِ محصول)
    خروجی: ماتریس شباهت (n x n) با استفاده از TF-IDF و cosine
    """
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
    if not corpus:
        return []
    vectorizer = TfidfVectorizer()
    X = vectorizer.fit_transform(corpus)
    sim_matrix = cosine_similarity(X, X)
    return sim_matrix

class Command(BaseCommand):
    help = "Add or edit a product and update similarity relations (TF-IDF on full corpus like offline script)"

    def handle(self, *args, **kwargs):
        if not os.path.exists(INPUT_PATH):
            self.stdout.write(self.style.ERROR(f"Input file not found: {INPUT_PATH}"))
            return

        with open(INPUT_PATH, "r", encoding="utf-8") as f:
            payload = json.load(f)

        action = payload.get("action", "new")
        product_data = payload.get("product", {})
        from products.models import Product

        # 1) جمع‌آوری همهٔ محصولات موجود و ساخت corpus اولیه (از tokens یا با تولید on-the-fly)
        all_products = list(Product.objects.all().order_by("id"))
        all_ids = []
        all_vecs = []  # رشته‌های مرکب برای TF-IDF
        id_to_index = {}
        for idx, p in enumerate(all_products):
            tok_list, vec = build_tokens_from_model_obj(p)
            all_ids.append(p.id)
            all_vecs.append(vec)
            id_to_index[p.id] = idx

        # 2) برای حالتِ edit: قرار است نسخهٔ جدیدِ محصول جایگزین نسخهٔ قدیمی شود.
        #    برای حالت new: محصول جدید را در ابتدای corpus اضافه می‌کنیم.
        if action == "edit":
            edit_id = product_data.get("id")
            if edit_id is None:
                self.stdout.write(self.style.ERROR("Edit action but no 'id' provided"))
                return
            # new tokens/vec for edited product
            new_tokens_dict, new_vec = build_tokens_from_payload(product_data)
            # replace in all_vecs if present, otherwise append (unlikely)
            if edit_id in id_to_index:
                replace_idx = id_to_index[edit_id]
                all_vecs[replace_idx] = new_vec
                self.stdout.write(f"DEBUG: replaced vec for product id={edit_id} at index={replace_idx}")
            else:
                # not found: append at end and remember its id
                all_ids.append(edit_id)
                all_vecs.append(new_vec)
                id_to_index[edit_id] = len(all_ids) - 1
                self.stdout.write(f"DEBUG: edit id {edit_id} not found among DB products, appended to corpus")
            # build full corpus where index_of_edited = id_to_index[edit_id]
            corpus = all_vecs[:]  # corpus aligned with all_ids
            # compute full sim matrix
            sim_matrix = compute_similarities_for_corpus(corpus)
            # find similar ids for edited product
            target_idx = id_to_index[edit_id]
            sims = sim_matrix[target_idx]
            similar_ids = [all_ids[j] for j in range(len(all_ids)) if j != target_idx and sims[j] >= SIM_THRESHOLD]
            self.stdout.write(f"DEBUG: similar_ids for edited product {edit_id}: {similar_ids}")
        else:
            # action == "new"
            new_tokens_dict, new_vec = build_tokens_from_payload(product_data)
            # corpus with new product at index 0 (same as offline: we can put new first)
            corpus = [new_vec] + all_vecs
            sim_matrix = compute_similarities_for_corpus(corpus)
            # sims between new (index 0) and others (1..)
            if len(corpus) >= 2:
                sims = sim_matrix[0]  # row 0
                similar_ids = [all_ids[i-1] for i in range(1, len(corpus)) if sims[i] >= SIM_THRESHOLD]
            else:
                similar_ids = []
            self.stdout.write(f"DEBUG: similar_ids for NEW product (pre-save): {similar_ids}")

        # 3) نوشتن در DB با transaction و سپس هم‌سان کردن similar_products سایر محصولات
        with transaction.atomic():
            if action == "new":
                # create, then use actual prod_obj.id
                prod_obj = Product.objects.create(
                    name=product_data.get('name', ''),
                    brand=product_data.get('brand', ''),
                    category=product_data.get('category', ''),
                    description=product_data.get('description', ''),
                    skin_type=product_data.get('skin_type', []),
                    suitable_for=product_data.get('suitable_for', []),
                    concerns_targeted=", ".join(product_data.get('suitable_for', [])) if product_data.get('suitable_for') else '',
                    tags=product_data.get('tags', []),
                    price=product_data.get('price', 0),
                    stock=product_data.get('stock', 0),
                    products_tokens=new_tokens_dict,
                    similar_products=similar_ids,
                    similarity_threshold=SIM_THRESHOLD,
                )
                new_id = prod_obj.id
                self.stdout.write(self.style.SUCCESS(f"Created product id={new_id}"))
                # حالا برو و برای هر محصول موجود در corpus بررسی کن که آیا new_id باید در لیست مشابه‌ها باشد
                # اگر در لیست similar_ids بود اضافه کن؛ در غیر این صورت حذف کن اگر قبلاً بود
                for other_id in all_ids:
                    try:
                        other = Product.objects.get(id=other_id)
                    except Product.DoesNotExist:
                        continue
                    lst = list(other.similar_products or [])
                    # آیا other مشابه new است؟
                    # در corpus، position of other is at index = all_ids.index(other_id) + 1 (چون new در index0)
                    # اما ما از similar_ids محاسبه‌شده استفاده می‌کنیم
                    if other_id in similar_ids:
                        if new_id not in lst:
                            lst.append(new_id)
                            other.similar_products = lst
                            other.save(update_fields=['similar_products'])
                    else:
                        if new_id in lst:
                            lst.remove(new_id)
                            other.similar_products = lst
                            other.save(update_fields=['similar_products'])
            elif action == "edit":
                edit_id = product_data.get("id")
                try:
                    prod_obj = Product.objects.get(id=edit_id)
                except Product.DoesNotExist:
                    self.stdout.write(self.style.ERROR(f"Product id={edit_id} not found."))
                    return
                # update fields & tokens & similar_products
                prod_obj.name = product_data.get('name', '')
                prod_obj.brand = product_data.get('brand', '')
                prod_obj.category = product_data.get('category', '')
                prod_obj.description = product_data.get('description', '')
                prod_obj.skin_type = product_data.get('skin_type', [])
                prod_obj.suitable_for = product_data.get('suitable_for', [])
                prod_obj.concerns_targeted = ", ".join(product_data.get('suitable_for', [])) if product_data.get('suitable_for') else ''
                prod_obj.tags = product_data.get('tags', [])
                prod_obj.price = product_data.get('price', 0)
                prod_obj.stock = product_data.get('stock', 0)
                prod_obj.products_tokens = new_tokens_dict
                prod_obj.similarity_threshold = SIM_THRESHOLD
                prod_obj.similar_products = similar_ids
                prod_obj.save()
                self.stdout.write(self.style.SUCCESS(f"Edited product id={edit_id} and set similar_products to {similar_ids}"))

                # همسان‌سازی سایر محصولات: اگر edited در similar_ids آنها باید باشد، اضافه کن؛ در غیر این صورت حذف کن
                for other_id in all_ids:
                    if other_id == edit_id:
                        continue
                    try:
                        other = Product.objects.get(id=other_id)
                    except Product.DoesNotExist:
                        continue
                    lst = list(other.similar_products or [])
                    if edit_id in similar_ids:
                        # edited similar to other? (we have symmetric condition via sim matrix at index)
                        # sims computed earlier corresponds to positions in corpus
                        # compute index in corpus for other:
                        # if edit replaced an existing index, we used that; else logic still holds
                        if edit_id not in lst:
                            lst.append(edit_id)
                            other.similar_products = lst
                            other.save(update_fields=['similar_products'])
                    else:
                        if edit_id in lst:
                            lst.remove(edit_id)
                            other.similar_products = lst
                            other.save(update_fields=['similar_products'])
            else:
                self.stdout.write(self.style.ERROR(f"Unknown action: {action}"))
                return

        self.stdout.write(self.style.SUCCESS(f"Done at {datetime.utcnow().isoformat()}"))