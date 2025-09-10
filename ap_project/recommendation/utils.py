
"""
cd ap_project
python recommendation/utils.py --user u1 --id 42

"""
import os, sys, json, django
from urllib.parse import parse_qs

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ap_project.settings")
django.setup()

def compute_product_score(user, product_id):
    # Import the scoring logic from recommendation.views (or wherever the main logic is)
    from recommendation.views import build_products_from_db, build_purchases_from_db, get_user_preferences_from_db, compute_recommendations
    products = build_products_from_db(user_id=user)
    purchases = build_purchases_from_db(user_id=user)
    user_prefs, keywords = get_user_preferences_from_db(user_id=user)
    recs = compute_recommendations(products, purchases, user_prefs or {}, keywords or {}, user_id=user)
    for r in recs['recommendations']:
        if str(r['product_id']) == str(product_id):
            return r.get('final_score', None)
    return None

def application(environ, start_response):
    # Parse query string
    params = parse_qs(environ.get('QUERY_STRING', ''))
    user = params.get('user', ['u1'])[0]
    product_id = params.get('id', [None])[0]
    if not product_id:
        start_response('400 Bad Request', [('Content-Type', 'application/json; charset=utf-8')])
        yield json.dumps({"error": "Missing id param"}, ensure_ascii=False).encode('utf-8')
        return
    score = compute_product_score(user, product_id)
    if score is None:
        start_response('404 Not Found', [('Content-Type', 'application/json; charset=utf-8')])
        yield json.dumps({"error": "Product not found for user"}, ensure_ascii=False).encode('utf-8')
    else:
        start_response('200 OK', [('Content-Type', 'application/json; charset=utf-8')])
        yield json.dumps({"score": score}, ensure_ascii=False).encode('utf-8')

# For command-line debug usage
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--user', default='u1')
    parser.add_argument('--id', required=True)
    args = parser.parse_args()
    score = compute_product_score(args.user, args.id)
    if score is None:
        print(json.dumps({"error": "Product not found for user"}, ensure_ascii=False, indent=2))
    else:
        print(json.dumps({"score": score}, ensure_ascii=False, indent=2))
