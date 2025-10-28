import argparse
import os
import jsonlines
import csv
from fetcher import fetch_html, load_local_html
from parsers import parse_search, parse_product
from bs4 import BeautifulSoup

def main(keyword, n=10, use_local_html=False):
    data_dir = 'data'
    html_dir = 'html_snapshots'
    os.makedirs(data_dir, exist_ok=True)
    search_filename = os.path.join(html_dir, 'search_page.html')
    
    if use_local_html:
        search_html = load_local_html(search_filename)
        if not search_html:
            print("No fallback HTML for search found. Please provide search_page.html in html_snapshots/. Exiting.")
            return
    else:
        search_url = f'https://www.amazon.com/s?k={keyword.replace(" ", "+")}'
        search_html = fetch_html(search_url)
        if search_html:
            print("Search HTML fetched successfully.") 
        else:
            print("Search HTML fetch failed.")
    
    product_previews = parse_search(search_html)
    if len(product_previews) < n:
        print(f"Found only {len(product_previews)} products. Proceeding with available data.")
    
    products = []
    product_html_base = None
    if use_local_html and os.path.exists(os.path.join(html_dir, 'product_pages.html')):
        product_html_base = load_local_html(os.path.join(html_dir, 'product_pages.html'))
        if not product_html_base:
            print("No fallback HTML for products found. Please provide product_pages.html in html_snapshots/. Exiting.")
            return

    for i, prev in enumerate(product_previews[:n], 1):
        if not prev.get('product_url'):
            print(f"Skipping product {i} due to invalid URL.")
            continue
        asin = prev.get('asin')  

        if use_local_html:
            if not product_html_base or not asin:
                print(f"No product HTML or ASIN for product {i}. Skipping.")
                continue
            # Extract the specific product section based on data-asin
            soup = BeautifulSoup(product_html_base, 'html.parser')
            product_div = soup.select_one(f'div[data-asin="{asin}"]')
            if not product_div:
                print(f"No product found for ASIN {asin} in local HTML. Skipping.")
                continue
            product_html = str(product_div) 
            details = parse_product(product_html)
        else:
            product_html = fetch_html(prev['product_url'])
            if not product_html:
                print(f"Failed to fetch product {i}. Skipping.")
                continue
            details = parse_product(product_html)

        if details:
            product = {**prev, **details}
            product.pop('product_url', None)  # Not needed in output
            products.append(product)
        else:
            print(f"No details parsed for product {i} (ASIN: {asin}). Skipping.")
    
    if not products:
        print("No products scraped.")
        return
    
    jsonl_path = os.path.join(data_dir, 'products.jsonl')
    with jsonlines.open(jsonl_path, mode='w') as writer:
        writer.write_all(products)
    
    csv_path = os.path.join(data_dir, 'products.csv')
    keys = products[0].keys()
    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        writer.writerows(products)
    
    print(f"Scraped {len(products)} products. Outputs: {jsonl_path}, {csv_path}")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Scrape top Amazon products by keyword.")
    parser.add_argument('--q', required=True, help="Search keyword (e.g., 'massage gun')")
    parser.add_argument('--n', type=int, default=10, help="Number of products (default: 10)")
    parser.add_argument('--use-local-html', action='store_true', help="Use local HTML fallback")
    args = parser.parse_args()
    main(args.q, args.n, args.use_local_html)