import os
import jsonlines
import csv
import re

def normalize_price(price_str):
    """Convert price string (e.g., 'PKR 84,676.80') to float."""
    if not price_str or price_str == '':
        return None
    # Remove currency code and commas, convert to float
    match = re.search(r'[\d,]+(?:\.\d+)?', price_str.replace(',', ''))
    if match:
        return float(match.group(0))
    return None

def normalize_weight(weight_str):
    """Convert weight to pounds, assuming input is in pounds or ounces."""
    if not weight_str or weight_str == 'No weight':
        return None
    weight_str = weight_str.lower().strip()
    if 'pounds' in weight_str or 'lb' in weight_str:
        return float(re.search(r'(\d+\.?\d*)', weight_str).group(1))
    elif 'ounces' in weight_str or 'oz' in weight_str:
        ounces = float(re.search(r'(\d+\.?\d*)', weight_str).group(1))
        return ounces / 16.0  # Convert ounces to pounds
    return None

def normalize_review_count(review_count_str):
    """Convert review count string (e.g., '2.3K', '2,300') to integer."""
    if not review_count_str or review_count_str == '':
        return None
    review_count_str = review_count_str.strip()
    # Handle 'K' for thousands
    if 'K' in review_count_str.upper():
        match = re.search(r'(\d+\.?\d*)K', review_count_str.upper())
        if match:
            value = float(match.group(1)) * 1000
            return int(value)
    # Handle commas (e.g., '2,300')
    match = re.search(r'(\d{1,3}(?:,\d{3})*)', review_count_str)
    if match:
        return int(match.group(1).replace(',', ''))
    # Handle plain numbers (e.g., '210')
    try:
        return int(review_count_str)
    except ValueError:
        return None

def is_valid_numeric(value, field_name):
    """Check if a value can be converted to a number (float for rating, int for review_count)."""
    if not value or value == '':
        return False
    try:
        if field_name == 'rating':
            float(value)  
            return 0 <= float(value) <= 5  
        elif field_name == 'review_count':
            normalized = normalize_review_count(value)
            return normalized is not None and normalized >= 0
    except ValueError:
        return False
    return False

def extract_product_data(product):
    """Extract standardized product data, skipping invalid ratings or review counts."""
    # Checking validity of rating and review_count
    rating = product.get('rating')
    review_count = product.get('review_count')
    if not (is_valid_numeric(rating, 'rating') and is_valid_numeric(review_count, 'review_count')):
        return None

    # Extracting valid data
    data = {
        'asin': product.get('asin', ''),
        'price': normalize_price(product.get('price', '')),
        'title': product.get('title', ''),
        'rating': float(product.get('rating')) if product.get('rating') else None,
        'review_count': normalize_review_count(product.get('review_count')),
        'brand': product.get('brand', '')    }
    return data

def compare_products():
    data_dir = 'data'
    input_file = os.path.join(data_dir, 'products.jsonl')
    output_file = os.path.join(data_dir, 'feature_matrix.csv')

    if not os.path.exists(input_file):
        print(f"Error: {input_file} not found. Please run the scrape first.")
        return

    products = []
    fieldnames = ['asin', 'price', 'title', 'rating', 'review_count', 'brand']

    with jsonlines.open(input_file, mode='r') as reader:
        for product in reader:
            extracted_data = extract_product_data(product)
            if extracted_data is not None:
                products.append(extracted_data)

    if not products:
        print("No valid products found in products.jsonl. All entries may have invalid ratings or review counts.")
        return

    # Writing to CSV 
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for product in products:
            writer.writerow(product)

    print(f"Feature matrix saved to {output_file} with {len(products)} valid products.")

if __name__ == '__main__':
    compare_products()