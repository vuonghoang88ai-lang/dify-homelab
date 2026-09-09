from bot_content import crawl_article
print("Testing mivietnam.vn:")
res = crawl_article("https://mivietnam.vn/quat-khong-canh-lumias-105/")
if res: print(res['title'], len(res['original_html']))
print("Testing xiaomihaiduong.vn:")
res = crawl_article("https://xiaomihaiduong.vn/pin-sac-cap-tai-nghe/")
if res: print(res['title'], len(res['original_html']))
