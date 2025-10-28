from bs4 import BeautifulSoup

def _extract_title(parent_item):
    """
    Robust title extraction.
    1. New layout → <div data-cy="title-recipe"> → <h2> (inside <a>)
    2. Old layout → <h2 class="a-size-base-plus">
    3. Ultimate fallback → any <h2> inside the card.
    """
    # 1. New layout
    title_recipe = parent_item.find('div', {'data-cy': 'title-recipe'})
    if title_recipe:
        h2 = title_recipe.find('h2')
        if h2:
            span = h2.find('span')
            return (span.get_text(strip=True) if span else h2.get_text(strip=True))

    # 2. Old layout
    h2 = parent_item.find_next('h2', class_='a-size-base-plus')
    if h2:
        return h2.get_text(strip=True)

    # 3. Fallback – any h2 inside the card
    h2 = parent_item.find('h2')
    if h2:
        return h2.get_text(strip=True)

    return ''          # title not found

def parse_search(html):
    soup = BeautifulSoup(html, 'html.parser')
    products = []

    for item in soup.select('div.s-product-image-container'):

        parent_item = item.find_parent('div', class_='s-result-item')
        if not parent_item or parent_item.get('data-component-type') != 's-search-result':
            continue
        if item.select_one('.puis-sponsored-label-text') or 'Sponsored' in item.text:
            continue

        link = item.select_one('a.a-link-normal.s-no-outline')
        if not link or not link.get('href'):
            continue
        href = link['href']
        asin_match = href.split('/dp/')[1].split('/')[0] if '/dp/' in href else ''
        if not asin_match:
            continue
        product_url = f"https://www.amazon.com/dp/{asin_match}"

        title = _extract_title(parent_item)          # <-- new helper


        price_span = parent_item.select_one('span.a-price span.a-offscreen')
        price = price_span.text.strip() if price_span else ''

        rating_span = parent_item.select_one('span.a-icon-alt')
        rating = rating_span.get_text(strip=True).split(' out of')[0] if rating_span else ''


        reviews_span = parent_item.select_one('a.s-link-style span.a-size-mini')
        review_count = ''
        if reviews_span:
            txt = reviews_span.get_text(strip=True)
            
            review_count = txt.strip('()').replace(',', '')
        else:
            
            old_span = parent_item.select_one('span.a-size-mini.puis-normal-weight-text')
            if old_span:
                review_count = old_span.get_text(strip=True).replace('(', '').replace(')', '').replace(',', '')

        image_tag = item.select_one('img.s-image')
        image_url = image_tag['src'] if image_tag else ''

        if not title:
            continue

        products.append({
            'asin': asin_match,
            'title': title,
            'price': price,
            'rating': rating,
            'review_count': review_count,
            'image_url': image_url,
            'product_url': product_url
        })

    return products[:10]          # keep only the first 10

def parse_product(html):
    soup = BeautifulSoup(html, 'html.parser')
    brand_tag = soup.select_one('#bylineInfo')
    brand = brand_tag.text.replace('Visit the ', '').replace(' Store', '').strip() if brand_tag else ''
    bullet_features = [li.text.strip() for li in soup.select('#feature-bullets ul li span') if li.text.strip()]
    dimensions = ''
    weight = ''
    tech_specs = soup.select('#productDetails_techSpec_section_1 tr')
    for tr in tech_specs:
        th = tr.select_one('th').text.strip().lower()
        td = tr.select_one('td').text.strip()
        if 'dimension' in th:
            dimensions = td
        if 'weight' in th:
            weight = td
    breadcrumbs = [span.text.strip() for span in soup.select('#wayfinding-breadcrumbs_feature_div ul li span.a-list-item') if span.text.strip()]
    category = ' > '.join(breadcrumbs)
    return {
        'brand': brand,
        'bullet_features': bullet_features,
        'dimensions': dimensions,
        'weight': weight,
        'category': category
    }