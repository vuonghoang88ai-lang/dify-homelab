import requests
from bs4 import BeautifulSoup
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

def get_pending_crawl_links():
    print("Đang tìm các bài viết đang chờ cào (status = 'pending_crawl')...")
    sql = "SELECT source_url FROM seo_articles WHERE status = 'pending_crawl'"
    result = execute_d1_query(sql)
    try:
        if result.get("success"):
            rows = result['result'][0]['results']
            return [row['source_url'] for row in rows]
    except Exception as e:
        print(f"Lỗi khi đọc DB: {e}")
    return []

# ==========================================
# CÀO NỘI DUNG (CONSUMER)
# ==========================================
def crawl_article(url):
    print(f"Đang cào bài: {url}")
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        title_tag = soup.find('h1')
        title = title_tag.text.strip() if title_tag else "Không có tiêu đề"
        
        # TỪ ĐIỂN CSS VẠN NĂNG (UNIVERSAL CLASSES)
        universal_classes = [
            'entry-content', 'post-content', 'elementor-widget-theme-post-content',
            'td-post-content', 'td-post-body', 'article-content',
            'content_detail', 'new_details_contents', 'detail_contents', 
            'show_details', 'main-content', 'post-detail'
        ]
        
        content_tag = None
        for css_class in universal_classes:
            content_tag = soup.find('div', class_=css_class) or soup.find('article', class_=css_class)
            if content_tag:
                break # Tìm thấy lớp áo bọc nội dung thì dừng tìm kiếm
                      
        content_html = ""
        if content_tag:
            # Xóa sạch các thẻ rác (script, style, iframe quảng cáo)
            for s in content_tag.select('script, style, iframe'):
                s.extract()
            content_html = str(content_tag)
            
        return {
            "title": title,
            "original_html": content_html,
            "source_url": url
        }
    except Exception as e:
        print(f"Lỗi khi cào {url}: {e}")
        return None

def update_article_in_d1(article_data):
    if not article_data or not article_data['original_html'] or article_data['original_html'] == "None":
        print(f"❌ Dữ liệu rỗng (Thường là Trang Sản Phẩm/Danh Mục), đánh dấu thất bại: {article_data['source_url']}")
        # Đánh dấu failed để lần sau không cào lại nữa
        sql = "UPDATE seo_articles SET status = 'failed' WHERE source_url = ?"
        execute_d1_query(sql, [article_data['source_url']])
        return
        
    sql = """
    UPDATE seo_articles 
    SET title = ?, original_html = ?, status = 'pending_ai'
    WHERE source_url = ?
    """
    params = [
        article_data['title'],
        article_data['original_html'],
        article_data['source_url']
    ]
    
    result = execute_d1_query(sql, params)
    if result.get("success"):
        print(f"✅ Đã tải và cập nhật thành công: {article_data['title']}")
    else:
        print(f"❌ Lỗi cập nhật bài viết: {result.get('errors', result)}")

if __name__ == "__main__":
    print("🚀 KHỞI ĐỘNG BOT CÀO NỘI DUNG")
    pending_urls = get_pending_crawl_links()
    
    if not pending_urls:
        print("🎉 Không có bài viết nào đang chờ cào!")
    else:
        print(f"🚀 Bắt đầu cào nội dung cho {len(pending_urls)} bài viết...")
        for url in pending_urls:
            data = crawl_article(url)
            update_article_in_d1(data)
            time.sleep(2) # Tránh bị server chặn
        print("✅ Đã hoàn thành quá trình tải Nội dung!")
