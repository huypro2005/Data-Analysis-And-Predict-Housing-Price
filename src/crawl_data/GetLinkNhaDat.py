from selenium import webdriver
import undetected_chromedriver as uc
import threading as threading
import bs4
import time
import traceback
import concurrent.futures
import psutil

def create_chrome_options():
    """Tạo ChromeOptions mới cho mỗi driver"""
    options = webdriver.ChromeOptions()
    options.add_argument("--start-maximized")  # mở to cửa sổ
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    return options

def get_data_with_retry(url, max_retries=3):
    """Lấy data với retry mechanism"""
    for attempt in range(max_retries):
        driver = None
        try:
            # Tạo options mới cho mỗi driver
            options = create_chrome_options()
            driver = uc.Chrome(options=options, version_main=145)
            pid = driver.browser_pid
            driver.get(url)
            time.sleep(2)  # Đợi trang load
            
            soup = bs4.BeautifulSoup(driver.page_source, 'html.parser')
            items = soup.find_all('a', class_='js__product-link-for-product-id')
            links = []
            for item in items:
                link = item.get('href')
                if link and not "lahome" in link:
                    links.append(url + link)

            if driver:
                try:
                    driver.quit()
                    driver = None
                except Exception as e:
                    print(f"Lỗi khi đóng driver: {e}")
            if pid:
                try:
                    p = psutil.Process(pid)
                    if p.is_running():
                        p.kill()
                except psutil.NoSuchProcess:
                    pass

            return links
        except (Exception, psutil.NoSuchProcess) as e:
            print(f"Lỗi lần {attempt + 1}/{max_retries} khi xử lý {url}: {e}")
            if attempt < max_retries - 1:
                time.sleep(5)  # Đợi 5 giây trước khi thử lại
            else:
                print(f"Không thể xử lý {url} sau {max_retries} lần thử")
            
            if driver:
                try:
                    driver.quit()
                    driver = None
                except Exception as e:
                    print(f"Lỗi khi đóng driver: {e}")
            if pid:
                try:
                    p = psutil.Process(pid)
                    if p.is_running():
                        p.kill()
                except psutil.NoSuchProcess:
                    pass

    return []



def crawl_all_pages():
    """Crawl tất cả các trang với xử lý lỗi tốt hơn"""
    with open('linkNhaDat.txt', 'a', encoding='utf-8') as f:
        for i in range(8, 1000):
            try:
                url = f'https://batdongsan.com.vn/nha-dat-ban-tp-hcm/p{i}'
                print(f'Đang xử lý trang {i}...')
                 
                links = get_data_with_retry(url)
                 
                if links:
                    for link in links:
                        f.write(link + '\n')
                    print(f'Đã lưu {len(links)} links từ trang {i}')
                else:
                    print(f'Không tìm thấy links ở trang {i}')
                 
                # Delay giữa các request để tránh bị block
                time.sleep(1)
                 
            except Exception as e:
                print(f"Lỗi khi xử lý trang {i}: {e}")
                traceback.print_exc()
                time.sleep(5)  # Đợi lâu hơn nếu có lỗi
                continue
    
    print('Done writing links to file.')

def crawl_single_page(page_num):
    """Crawl một trang cụ thể và trả về links"""
    try:
        url = f'https://batdongsan.com.vn/nha-dat-ban-tp-hcm/p{page_num}'
        print(f'Đang xử lý trang {page_num}...')
        
        links = get_data_with_retry(url)
        
        if links:
            print(f'Đã tìm thấy {len(links)} links từ trang {page_num}')
            return page_num, links
        else:
            print(f'Không tìm thấy links ở trang {page_num}')
            return page_num, []
            
    except Exception as e:
        print(f"Lỗi khi xử lý trang {page_num}: {e}")
        return page_num, []

def crawl_with_multithreading(start_page=1, end_page=25, max_workers=6):
    """Crawl nhiều trang cùng lúc với multithreading"""
    all_links = {}
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Tạo futures cho tất cả các trang
        future_to_page = {
            executor.submit(crawl_single_page, page_num): page_num 
            for page_num in range(start_page, end_page + 1)
        }
        
        # Xử lý kết quả khi hoàn thành
        for future in concurrent.futures.as_completed(future_to_page):
            page_num = future_to_page[future]
            try:
                page_num, links = future.result()
                if links:
                    with open('./linkNhaDat.txt', 'a', encoding='utf-8') as f:
                        for link in links:
                            f.write(link + '\n')
                    print(f'Đã lưu {len(links)} links từ trang {page_num}')
            except Exception as e:
                print(f"Lỗi khi xử lý kết quả trang {page_num}: {e}")
    
    print(f'Hoàn thành! Đã crawl {len(all_links)} trang với tổng cộng {sum(len(links) for links in all_links.values())} links')

if __name__ == "__main__":
    # Crawl từ trang 1 đến 50 với 3 worker threads
    crawl_with_multithreading(start_page=1, end_page=25, max_workers=6)
    # crawl_single_page(1000)


