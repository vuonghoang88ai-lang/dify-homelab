import requests
from bs4 import BeautifulSoup
import time
from urllib.parse import urlparse

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

def get_existing_product_urls():
    print("Đang lấy danh sách các SẢN PHẨM đã cào từ Cloudflare D1...")
    sql = "SELECT source_url FROM seo_products"
    result = execute_d1_query(sql)
    existing_urls = set()
    try:
        if result.get("success"):
            rows = result['result'][0]['results']
            existing_urls = set(row['source_url'] for row in rows)
            print(f"Đã tìm thấy {len(existing_urls)} sản phẩm trong Database.")
    except Exception as e:
        print(f"Lỗi khi đọc DB: {e}")
    return existing_urls

def get_existing_article_urls():
    sql = "SELECT source_url FROM seo_articles"
    result = execute_d1_query(sql)
    existing_urls = set()
    try:
        if result.get("success"):
            rows = result['result'][0]['results']
            existing_urls = set(row['source_url'] for row in rows)
    except Exception as e:
        pass
    return existing_urls

def save_product_link_to_d1(url):
    sql = """
    INSERT INTO seo_products (source_url, title, status) 
    VALUES (?, '', 'pending_crawl')
    """
    params = [url]
    result = execute_d1_query(sql, params)
    if result.get("success"):
        print(f"✅ Đã thêm Link Sản Phẩm vào hàng chờ: {url}")
    else:
        print(f"⚠️ Link đã tồn tại trong DB, bỏ qua: {url}")

# ==========================================
# CÀO LINK SẢN PHẨM
# ==========================================
def get_product_links(category_url):
    print(f"Đang quét danh mục sản phẩm: {category_url}")
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    parsed_uri = urlparse(category_url)
    domain = '{uri.netloc}'.format(uri=parsed_uri).replace('www.', '')
    
    try:
        response = requests.get(category_url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        links = []
        # Quét TẤT CẢ các thẻ <a> trong khu vực chứa sản phẩm
        # Đa số các web dùng class 'product' hoặc 'woocommerce-loop-product__link'
        product_blocks = soup.find_all(class_=['product', 'item-product', 'product-item', 'type-product'])
        
        if product_blocks:
            # Nếu tìm thấy block sản phẩm cụ thể
            for block in product_blocks:
                a_tag = block.find('a', href=True)
                if a_tag:
                    href = a_tag['href']
                    if domain in href:
                        links.append(href)
        else:
            # Thu thập bừa và lọc bằng regex hoặc heuristic nếu web ko code chuẩn
            for a_tag in soup.find_all('a', href=True):
                href = a_tag['href']
                if len(href) > 30 and domain in href and not '/category/' in href and not '/danh-muc/' in href:
                    links.append(href)
        
        return list(set(links))
    except Exception as e:
        print(f"Lỗi khi quét danh mục: {e}")
        return []

if __name__ == "__main__":
    print("🚀 KHỞI ĐỘNG BOT QUÉT LINK SẢN PHẨM (PRODUCT CRAWLER)")
    SITES = [
        # MI VIỆT NAM (Sử dụng /page/2)
        {"url": "https://mivietnam.vn/tivi-xiaomi", "pagination": "slash"},
        {"url": "https://mivietnam.vn/robot-hut-bui", "pagination": "slash"},
        
        # XIAOMI HẢI DƯƠNG (Sử dụng /page/2)
        {"url": "https://xiaomihaiduong.vn/tivi-xiaomi/", "pagination": "slash"},
        {"url": "https://xiaomihaiduong.vn/robot-hut-bui-don-nha/", "pagination": "slash"},
        
        # TỔNG KHO XIAOMI (Sử dụng ?page=2)
        {"url": "https://tongkhoxiaomi.vn/tivi-4k-hdr", "pagination": "query"},
        {"url": "https://tongkhoxiaomi.vn/robot-may-hut-bui", "pagination": "query"},
        
        # HƯỚNG DẪN THÊM LINK MỚI:
        # Bạn chỉ cần copy link của bất kỳ thư mục danh mục sản phẩm nào và dán vào đây!
        # Nếu web dùng ?page=2 thì để là "query", nếu dùng /page/2/ thì để là "slash".
    ]
    
    existing_urls = get_existing_product_urls()
    
    # Đối chiếu chéo với bảng Bài viết
    existing_article_urls = get_existing_article_urls()
    if existing_article_urls:
        print(f"Đã tải {len(existing_article_urls)} link Bài viết để đối chiếu chéo (Blacklist).")
        existing_urls.update(existing_article_urls)
        
    all_product_links = []
    
    for site in SITES:
        base_category_link = site["url"]
        pagination_type = site["pagination"]
        print(f"\n==============================================")
        print(f"BẮT ĐẦU QUÉT DANH MỤC: {base_category_link}")
        print(f"==============================================")
        
        page = 1
        seen_links_this_run = set()
        
        while True:
            if page == 1:
                url = base_category_link
            else:
                if pagination_type == "slash":
                    url = f"{base_category_link.rstrip('/')}/page/{page}/"
                else:
                    url = f"{base_category_link}?page={page}"
                    
            links = get_product_links(url)
            
            if not links:
                print(f"Trang {page} rỗng. Đã quét xong.")
                break
                
            links_not_seen_in_this_run = [l for l in links if l not in seen_links_this_run]
            if not links_not_seen_in_this_run:
                print(f"Trang {page} trả về trùng lặp (Phân trang ảo). Dừng quét danh mục này!")
                break
            seen_links_this_run.update(links)
                
            new_links = [l for l in links if l not in existing_urls]
            if not new_links:
                print(f"Trang {page} toàn sản phẩm cũ. Bỏ qua trang sau.")
                break
                
            all_product_links.extend(new_links)
            page += 1
            time.sleep(1)
        
    unique_new_links = list(set(all_product_links))
    
    if not unique_new_links:
        print("\n🎉 Không có sản phẩm nào mới!")
    else:
        print(f"\n🚀 Bắt đầu lưu {len(unique_new_links)} Sản phẩm MỚI vào Database...")
        for url in unique_new_links:
            save_product_link_to_d1(url)
        print("✅ Đã hoàn thành quét Link Sản Phẩm!")
