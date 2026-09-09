import requests
from bs4 import BeautifulSoup
import json
import time

# ==========================================
# CẤU HÌNH CLOUDFLARE D1
# ==========================================
CLOUDFLARE_ACCOUNT_ID = 'f9987a2c3f3b2dc291b1b3b222aa17f2'
CLOUDFLARE_DB_ID = 'd3aa2c55-4d9c-43c6-b26f-5b5de686f130'
CLOUDFLARE_API_TOKEN = 'cfut_bvmWJJhZc9Kl5tD9Xi9rm8G3NClkRBQ3sRZtatR4e5c307b4'

D1_API_URL = f"https://api.cloudflare.com/client/v4/accounts/{CLOUDFLARE_ACCOUNT_ID}/d1/database/{CLOUDFLARE_DB_ID}/query"

headers_d1 = {
    "Authorization": f"Bearer {CLOUDFLARE_API_TOKEN}",
    "Content-Type": "application/json"
}

def execute_d1_query(sql, params=[]):
    payload = {
        "sql": sql,
        "params": params
    }
    response = requests.post(D1_API_URL, headers=headers_d1, json=payload)
    return response.json()

def get_pending_products():
    print("Đang tìm các sản phẩm đang chờ cào (status = 'pending_crawl')...")
    sql = "SELECT source_url FROM seo_products WHERE status = 'pending_crawl'"
    result = execute_d1_query(sql)
    try:
        if result.get("success"):
            rows = result['result'][0]['results']
            return [row['source_url'] for row in rows]
    except Exception as e:
        print(f"Lỗi khi đọc DB: {e}")
    return []

# ==========================================
# CÀO NỘI DUNG WOOCOMMERCE
# ==========================================
def crawl_product(url):
    print(f"Đang cào sản phẩm: {url}")
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        response = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 1. TIÊU ĐỀ
        title_tag = soup.find('h1', class_='product_title') or soup.find('h1')
        title = title_tag.text.strip() if title_tag else "Không có tiêu đề"
        
        # 2. GIÁ (Price)
        price_tag = soup.find('p', class_='price') or soup.find('div', class_='product-price')
        price_html = str(price_tag) if price_tag else ""
        
        # 3. HÌNH ẢNH (Gallery)
        images = []
        gallery = soup.find(class_='woocommerce-product-gallery')
        if gallery:
            for img_link in gallery.find_all('a', href=True):
                img_url = img_link['href']
                if img_url.endswith(('.jpg', '.png', '.jpeg', '.webp')):
                    images.append(img_url)
        elif soup.find(class_='product-gallery'):
            for img in soup.find(class_='product-gallery').find_all('img'):
                if img.get('src'): images.append(img['src'])
                
        # Lấy ảnh đại diện nếu không có gallery
        if not images:
            img = soup.find('img', class_='wp-post-image')
            if img and img.get('src'):
                images.append(img['src'])
        
        # 4. THUỘC TÍNH (Attributes / Thông số kỹ thuật)
        attributes = ""
        attr_table = soup.find('table', class_='shop_attributes')
        if attr_table:
            attributes = str(attr_table)
            
        # 5. MÔ TẢ (Description)
        description_html = ""
        
        # Danh sách các class phổ biến chứa mô tả sản phẩm (WooCommerce, Flatsome, Custom)
        product_content_classes = [
            'tab-description', 'woocommerce-Tabs-panel--description', 'product-description',
            'content_product', 'card-description', 'content-product-showmore',
            'woocommerce-product-details__short-description', 'entry-content', 'content_detail'
        ]
        
        desc_tab = None
        for cls in product_content_classes:
            desc_tab = soup.find(id=cls) or soup.find(class_=cls)
            if desc_tab:
                # Nếu tìm thấy class này nhưng nội dung quá ngắn, tiếp tục tìm class khác
                if len(str(desc_tab)) > 500:
                    break
        
        if desc_tab:
            for s in desc_tab.select('script, style, iframe'):
                s.extract()
            description_html = str(desc_tab)
            
        if not description_html or len(description_html) < 200:
            return None # Coi như rỗng hoặc không phải trang sản phẩm chuẩn
            
        return {
            "title": title,
            "price": price_html,
            "images": json.dumps(list(set(images))),
            "attributes": attributes,
            "original_html": description_html,
            "source_url": url
        }
    except Exception as e:
        print(f"Lỗi khi cào {url}: {e}")
        return None

def update_product_in_d1(product_data, url):
    if not product_data:
        print(f"❌ Dữ liệu rỗng hoặc lỗi, đánh dấu thất bại: {url}")
        sql = "UPDATE seo_products SET status = 'failed' WHERE source_url = ?"
        execute_d1_query(sql, [url])
        return
        
    sql = """
    UPDATE seo_products 
    SET title = ?, price = ?, images = ?, attributes = ?, original_html = ?, status = 'pending_ai'
    WHERE source_url = ?
    """
    params = [
        product_data['title'],
        product_data['price'],
        product_data['images'],
        product_data['attributes'],
        product_data['original_html'],
        product_data['source_url']
    ]
    
    result = execute_d1_query(sql, params)
    if result.get("success"):
        print(f"✅ Đã cập nhật thành công sản phẩm: {product_data['title']}")
    else:
        print(f"❌ Lỗi cập nhật: {result.get('errors', result)}")

if __name__ == "__main__":
    print("🚀 KHỞI ĐỘNG BOT CÀO NỘI DUNG SẢN PHẨM (PRODUCT CRAWLER)")
    pending_urls = get_pending_products()
    
    if not pending_urls:
        print("🎉 Không có sản phẩm nào đang chờ cào!")
    else:
        print(f"🚀 Bắt đầu cào nội dung cho {len(pending_urls)} sản phẩm...")
        for url in pending_urls:
            product_data = crawl_product(url)
            update_product_in_d1(product_data, url)
            time.sleep(1) # Tránh bị block IP
        
        print("✅ Hoàn thành toàn bộ danh sách chờ!")
