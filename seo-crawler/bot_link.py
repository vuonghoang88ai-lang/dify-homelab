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

def get_existing_urls_from_d1():
    print("Đang lấy danh sách các bài đã cào từ Cloudflare D1...")
    sql = "SELECT source_url FROM seo_articles"
    result = execute_d1_query(sql)
    existing_urls = set()
    try:
        if result.get("success"):
            rows = result['result'][0]['results']
            existing_urls = set(row['source_url'] for row in rows)
            print(f"Đã tìm thấy {len(existing_urls)} bài viết trong Database.")
    except Exception as e:
        print(f"Lỗi khi đọc DB: {e}")
    return existing_urls

def get_existing_product_urls_from_d1():
    sql = "SELECT source_url FROM seo_products"
    result = execute_d1_query(sql)
    existing_urls = set()
    try:
        if result.get("success"):
            rows = result['result'][0]['results']
            existing_urls = set(row['source_url'] for row in rows)
    except Exception as e:
        pass
    return existing_urls
    

def save_link_to_d1(url):
    sql = """
    INSERT INTO seo_articles (source_url, title, original_html, status) 
    VALUES (?, '', '', 'pending_crawl')
    """
    params = [url]
    result = execute_d1_query(sql, params)
    if result.get("success"):
        print(f"✅ Đã thêm Link vào hàng chờ: {url}")
    else:
        print(f"⚠️ Link đã tồn tại trong DB, bỏ qua: {url}")

# ==========================================
# CÀO LINK (PRODUCER)
# ==========================================
def get_article_links(category_url):
    print(f"Đang quét danh mục: {category_url}")
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    # Lấy domain gốc để lọc link nội bộ
    parsed_uri = urlparse(category_url)
    domain = '{uri.netloc}'.format(uri=parsed_uri).replace('www.', '')
    
    try:
        response = requests.get(category_url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        links = []
        for a_tag in soup.find_all('a', href=True):
            href = a_tag['href']
            # Lọc link: đủ độ dài, không phải link chuyên mục tin tức, và thuộc domain hiện tại
            if len(href) > 40 and not href.endswith('/tin-tuc/') and domain in href:
                links.append(href)
        
        return list(set(links))
    except Exception as e:
        print(f"Lỗi khi quét danh mục: {e}")
        return []

if __name__ == "__main__":
    print("🚀 KHỞI ĐỘNG BOT QUÉT LINK ĐA NỀN TẢNG (UNIVERSAL)")
    SITES = [
        {"url": "https://viomiviet.vn/tin-tuc", "pagination": "query"},
        {"url": "https://mivietnam.vn/tin-tuc", "pagination": "slash"},
        {"url": "https://tongkhoxiaomi.vn/tin-tuc", "pagination": "slash"},
        {"url": "https://tivixiaomi.vn/tin-tuc", "pagination": "slash"},
        {"url": "https://xiaomihaiduong.vn/tin-tuc", "pagination": "slash"}
    ]
    
    existing_urls = get_existing_urls_from_d1()
    
    # Đối chiếu chéo với bảng Sản phẩm
    existing_product_urls = get_existing_product_urls_from_d1()
    if existing_product_urls:
        print(f"Đã tải {len(existing_product_urls)} link Sản phẩm để đối chiếu chéo (Blacklist).")
        existing_urls.update(existing_product_urls)

    all_article_links = []
    
    for site in SITES:
        base_category_link = site["url"]
        pagination_type = site["pagination"]
        print(f"\n==============================================")
        print(f"BẮT ĐẦU QUÉT WEBSITE: {base_category_link}")
        print(f"==============================================")
        
        page = 1
        seen_links_this_run = set() # Theo dõi TẤT CẢ các link đã gặp ở web này
        
        while True:
            # Xử lý cấu trúc phân trang khác nhau
            if page == 1:
                url = base_category_link
            else:
                if pagination_type == "slash":
                    url = f"{base_category_link.rstrip('/')}/page/{page}/"
                else:
                    url = f"{base_category_link}?page={page}"
                    
            links = get_article_links(url)
            
            if not links:
                print(f"Trang {page} rỗng. Đã quét xong toàn bộ danh mục của website này.")
                break
                
            # CHỐNG LẶP VÔ HẠN (Phân trang ảo)
            links_not_seen_in_this_run = [l for l in links if l not in seen_links_this_run]
            if not links_not_seen_in_this_run:
                print(f"Trang {page} trả về toàn bài cũ bị lặp lại của trang trước (Lỗi phân trang ảo). Chuyển web tiếp theo!")
                break
            seen_links_this_run.update(links)
                
            # TỐI ƯU HÓA: DỪNG SỚM NẾU GẶP TOÀN BÀI ĐÃ CÓ TRONG DB
            new_links = [l for l in links if l not in existing_urls]
            if not new_links:
                print(f"Trang {page} toàn link cũ đã có trong DB. Chắc chắn các trang sau cũng cũ. Chuyển sang web tiếp theo!")
                break
                
            all_article_links.extend(new_links)
            page += 1
            time.sleep(1)
        
    unique_new_links = list(set(all_article_links))
    
    if not unique_new_links:
        print("\n🎉 Tuyệt vời! Không có Link bài viết nào mới trên TẤT CẢ các website!")
    else:
        print(f"\n🚀 Bắt đầu lưu {len(unique_new_links)} Link MỚI vào Database...")
        for url in unique_new_links:
            save_link_to_d1(url)
        print("✅ Đã hoàn thành quá trình quét Link trên diện rộng!")
