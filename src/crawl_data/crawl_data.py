from pathlib import Path
import os
from time import time

# Xóa sạch file và folder cũ trong C:\Users\huy\AppData\Roaming\undetected_chromedriver
chrome_data_path = os.path.expanduser("~\\AppData\\Roaming\\undetected_chromedriver")
if os.path.exists(chrome_data_path):
    for root, dirs, files in os.walk(chrome_data_path, topdown=False):
        for name in files:
            try:
                os.remove(os.path.join(root, name))
            except Exception as e:
                print(f"Không thể xóa file {name}: {e}")
        for name in dirs:
            try:
                os.rmdir(os.path.join(root, name))
            except Exception as e:
                print(f"Không thể xóa folder {name}: {e}")



from crawl_data.src.crawl_data.GetLinkNhaDat import crawl_with_multithreading
from crawl_data.src.crawl_data.LocDataLink import get_property_details


if __name__ == "__main__":
    # tạo file links.txt nếu chưa tồn tại
    print("Đang chuẩn bị file linkNhaDat.txt và data1.json...")
    Path('linkNhaDat.txt').touch(exist_ok=True)
    Path("data1.json").touch(exist_ok=True)
    print("Chuẩn bị xong file linkNhaDat.txt và data1.json. Bắt đầu crawl links...")
    time.sleep(2)  # Đợi 2 giây trước khi bắt đầu crawl links

    # Bước 1: Crawl links với multithreading
    crawl_with_multithreading(start_page=1, end_page=2000, max_workers=6)

    print("--------------------")
    print("Đã hoàn thành bước 1: Crawl links. Bắt đầu bước 2: Lọc data từ links đã crawl.")
    print("--------------------")
    
    # Bước 2: Lọc data từ links đã crawl
    with open("linkNhaDat.txt", "r") as f:
        links = [line.strip() for line in f if line.strip()]
    get_property_details(links)