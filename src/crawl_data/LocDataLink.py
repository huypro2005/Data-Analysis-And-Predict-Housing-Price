import undetected_chromedriver as uc
from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium import webdriver
from urllib.parse import urlparse, parse_qs
import concurrent.futures
import re
import html as html_lib
import time
import json
import sys, os
import psutil
import threading


LOCK_DRIVER = threading.Lock()


ADDRESS_ = {
    'bình chánh':0, 
    'bình tân':1,  #
    'bình thạnh':2, #
    'cần giờ':3,
    'củ chi':4,
    'gò vấp':5,#
    'hóc môn':6,
    'nhà bè':7,
    'phú nhuận':8,
    'quận 1':9,
    'quận 10':10,
    'quận 11':11,
    'quận 12':12,#
    'quận 2':13,#
    'quận 3':14,
    'quận 4':15,
    'quận 5':16,
    'quận 6':17,
    'quận 7':18,#
    'quận 8':19,
    'quận 9':20,#
    'thủ đức':21,#
    'tân bình':22,#
    'tân phú':23 #
}
'''
Địa chỉ: 21, Số lượng: 2172
Địa chỉ: 20, Số lượng: 1760
Địa chỉ: 13, Số lượng: 1600
Địa chỉ: 18, Số lượng: 1240
Địa chỉ: 22, Số lượng: 1178
Địa chỉ: 23, Số lượng: 998
Địa chỉ: 2, Số lượng: 794
Địa chỉ: 12, Số lượng: 774
Địa chỉ: 5, Số lượng: 612
Địa chỉ: 1, Số lượng: 592
Địa chỉ: 9, Số lượng: 558
Địa chỉ: 10, Số lượng: 484
Địa chỉ: 6, Số lượng: 480
Địa chỉ: 7, Số lượng: 374
Địa chỉ: 8, Số lượng: 356
Địa chỉ: 0, Số lượng: 338
Địa chỉ: 14, Số lượng: 324
Địa chỉ: 19, Số lượng: 184
Địa chỉ: 17, Số lượng: 108
Địa chỉ: 15, Số lượng: 92
Địa chỉ: 4, Số lượng: 84
Địa chỉ: 11, Số lượng: 78
Địa chỉ: 16, Số lượng: 60
Địa chỉ: 3, Số lượng: 22
'''


REAL_ESTATE_ = {
    'căn hộ chung cư': 0,
    'chung cư mini, căn hộ dịch vụ': 1, # X
    'nhà riêng': 2, 
    'nhà biệt thự, liền kề':3,
    'nhà mặt phố': 4,
    'shophouse, nhà phố thương mại': 5,# X
    'đất nền dự án': 6, # X
    'bán đất': 7,
    'condotel': 8, # X
    'kho nhà xưởng': 9 # X
}

MONEY_UNIT = {
    'tỷ': 1000,
    'triệu': 1,
    'tr': 1
}

INTERIOR = {
    'sổ đỏ': 1,
    'sổ hồng': 1,
    'phap lý': 1,
    'pháp lý': 1,
    'hợp đồng': 2
}

def create_chrome_options():
    """Tạo ChromeOptions mới cho mỗi driver"""
    options = webdriver.ChromeOptions()
    options.add_argument("--start-maximized")  # mở to cửa sổ
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    return options

def check_real_estate(real_estate_text):
    for key, value in REAL_ESTATE_.items():
        if key in real_estate_text.lower():
            return value
    return None

print('Starting...')
with open('./linkNhaDat.txt', 'r', encoding='utf-8') as f:
    links0 = [ln.strip() for ln in f if ln.strip()]

# cách 180 số
# links = links0[26050:26080]


def get_page_source(link, max_retries=3):

    for attempt in range(max_retries):
        driver = None
        try:
            # Tạo options mới cho mỗi driver
            options = create_chrome_options()

            driver = uc.Chrome(options=options, version_main=145)
            pid = driver.browser_pid # Lấy PID của trình duyệt
            driver.get(link)
            time.sleep(0.5)
            page_html = driver.page_source
            soup = BeautifulSoup(page_html, "lxml")
            data = parse_detail(soup)
            
            if (not data or 
                data.get('loại nhà đất') is None or 
                data.get('địa chỉ') is None or 
                data.get('giá') is None or 
                data.get('diện tích') is None or 
                data.get('giá/m2') is None):
                print(f"Error parsing {link}, skipping...")
                if driver:
                    try:
                        driver.quit()
                    except Exception as e:
                        print(f"Lỗi khi đóng driver: {e}")
                    driver = None
                    # Giải phóng bộ nhớ
                    if pid:
                        try:
                            p =psutil.Process(pid)
                            if p.is_running():
                                p.kill()
                        except psutil.NoSuchProcess:
                            pass
                break
            

            if driver:
                try:
                    driver.quit()
                    driver = None
                except Exception as e:
                    print(f"Lỗi khi đóng driver: {e}")
            # Giải phóng bộ nhớ
            if pid:
                try:
                    p =psutil.Process(pid)
                    if p.is_running():
                        p.kill()
                except psutil.NoSuchProcess:
                    pass


            try:
                with open('./data1.json', 'a', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False)
                    f.write('\n')
                
            except Exception as e:
                print(f"Error saving data for {link}: {e}")
            break  # Thoát vòng lặp nếu thành công
        
        
        except Exception as e:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            print(exc_type, fname, exc_tb.tb_lineno)
            if driver:
                try:
                    driver.quit()
                    driver = None
                except Exception as e:
                    print(f"Lỗi khi đóng driver: {e}")
            # Giải phóng bộ nhớ
            if pid:
                try:
                    p =psutil.Process(pid)
                    if p.is_running():
                        p.kill()
                except psutil.NoSuchProcess:
                    pass

            if attempt < max_retries - 1:
                time.sleep(5)


       



def classify_price_and_pricePerM2(value, ext):
    if ext:
        if 'm²' in value:
            value, ext = ext, value
        return keep_number(value), keep_number(ext)
    else:
        return keep_number(value), None

def handle_interior_text(value):
    if 'sổ đỏ' in value.lower():
        return 1
    elif 'sổ hồng' in value.lower():
        return 1
    elif 'pháp lý' in value.lower():
        return 1
    elif 'hợp đồng' in value.lower():
        return 2
    return None



def _norm_text(s):
    return " ".join(s.split()).strip() if s else None

# giữ lại số bỏ đi các thông tin không cần thiết, có thể là số thập phân
def keep_number(text):
    num = re.sub(r'[^0-9.,]', '', text)
    if ',' in num:
        num = num.replace(',', '.')
    if 'tỷ' in text:
        return float(num) * 1000
    elif 'triệu' in text:
        return float(num)
    else:
        return float(num)


def extract_text(desc: str):
    patterns = {
        'mặt tiền': r"(mặt tiền[^\d]*)(\d+(?:[\.,]\d+)?\s*(?:m|m2|m²))",
        # 'kích thước': r"(\d+(?:[\.,]\d+)?)\s*[mM]*\s*[xX]\s*(\d+(?:[\.,]\d+)?)\s*[mM]*",
        'phòng ngủ': r"(\d+)\s*(?:pn|phòng ngủ)",
        'số tầng': r"(\d+)\s*(?:tầng|lầu|trệt|tầng trệt)",
        'pháp lý': r"(pháp lý|sổ hồng|sổ đỏ)[^\n\.,]*"
    }
    data = {
        'mặt tiền': None,
        'phòng ngủ': None,
        'pháp lý': None,
        'số tầng': None
    }

    for key, pattern in patterns.items():
        match = re.match(pattern, desc, re.IGNORECASE)
        if match:
            if key == 'mặt tiền':
                data['mặt tiền'] = keep_number(match.group(2))
            elif key == 'phòng ngủ':
                data['phòng ngủ'] = int(match.group(1))
            elif key == 'số tầng':
                data['số tầng'] = int(match.group(1))
            elif key == 'pháp lý':
                data['pháp lý'] = handle_interior_text(match.group(0))


    return data

def parse_detail(soup: BeautifulSoup) -> dict:
    data = {
       'loại nhà đất': None,
       'địa chỉ': None,
       'giá': None,
       'diện tích': None,
       'giá/m2': None,
       'mặt tiền': None,
       'phòng ngủ': None,
       'pháp lý': None,
       'tọa độ': None,
       'tọa độ x': None, # * 1000000
       'tọa độ y': None, # * 1000000
       'số tầng': None,
       
    }
    # --- 0) Loại nhà đất, địa chỉ ---
    real_estate = soup.find('a', class_='re__link-se', attrs={'level':'4'})
    address = soup.find('a', class_='re__link-se', attrs={'level':'3'})
    address_text = address.get_text()
    real_estate_text = real_estate.get_text()
    data['loại nhà đất'] = check_real_estate(real_estate_text)
    data['địa chỉ'] = ADDRESS_[address_text.lower()]



    # --- 1) Giá, diện tích, mặt tiền
    # --- 2) Diện tích, mặt tiền
    # --- 3) Phòng ngủ
    short_items = soup.select(".re__pr-short-info-item.js__pr-short-info-item")
    
    for i,item in enumerate(short_items):
        if i > 2:
            break
        label_el = item.select_one(".re__pr-short-info-title, .re__short-info-title, .title")
        value_el = item.select_one(".re__pr-short-info-value, .re__short-info-value, .value")
        ext_el = item.select_one(".re__pr-short-info-value, .re__short-info-value, .ext")

        if label_el:
            label = _norm_text(label_el.get_text(" ", strip=True))
        if value_el:
            value = _norm_text(value_el.get_text(" ", strip=True))
        if ext_el:
            ext = _norm_text(ext_el.get_text(" ", strip=True))
        else:
            ext = None
        if label and value:
            if "khoảng giá" in label.lower() or 'mức giá' in label.lower():
                if value.lower() == 'thỏa thuận':
                    return None
                data['giá'], data['giá/m2'] = classify_price_and_pricePerM2(value, ext)
            elif "Diện tích" in label:
                data['diện tích'] = keep_number(str(value))
                if ext:
                    data['mặt tiền'] = keep_number(str(ext))
                if data['giá/m2'] is None:
                    data['giá/m2'] = data['giá'] / data['diện tích']
            elif "Phòng ngủ" in label:
                data['phòng ngủ'] = int(keep_number(str(value)))

    

    # --- 4) Iframe map + toạ độ ---
    iframe = soup.select_one("div.re__section-body.js__section-body iframe")
    if iframe:
        src = iframe.get("src") or iframe.get("data-src")
        if src:
            src = html_lib.unescape(src)   # &amp; -> &

            # Thử đọc toạ độ từ query param
            lat = lng = None
            parsed = urlparse(src)
            qs = parse_qs(parsed.query)

            def _try_split(val):
                parts = [p.strip() for p in val.split(",")]
                if len(parts) >= 2:
                    return parts[0], parts[1]
                return None, None

            if "q" in qs and qs["q"]:
                a, b = _try_split(qs["q"][0])
                if a and b:
                    try:
                        lat, lng = float(a), float(b)
                    except ValueError:
                        pass

            if (lat is None or lng is None) and ("center" in qs and qs["center"]):
                a, b = _try_split(qs["center"][0])
                if a and b:
                    try:
                        lat, lng = float(a), float(b)
                    except ValueError:
                        pass

            # Fallback: regex bắt cặp số
            if lat is None or lng is None:
                m = re.search(r'([+-]?\d+(?:\.\d+)?),\s*([+-]?\d+(?:\.\d+)?)', src)
                if m:
                    try:
                        lat, lng = float(m.group(1)), float(m.group(2))
                    except ValueError:
                        pass

            if lat is not None and lng is not None:
                data["tọa độ x"] = lat*1000000000
                data["tọa độ y"] = lng*1000000000

    

    # --- 6) Thông tin chi tiết ---
    for item in soup.select(".re__pr-specs-content-item"):
        title_el = item.select_one(".re__pr-specs-content-item-title")
        value_el = item.select_one(".re__pr-specs-content-item-value")
        title = _norm_text(title_el.get_text(" ", strip=True)) if title_el else None
        value = _norm_text(value_el.get_text(" ", strip=True)) if value_el else None
        if title and value:
            key_lc = title.lower()
            if "mức giá" in key_lc or "khoảng giá" in key_lc:
                if data['giá'] is None:
                    data['giá'] = keep_number(str(value))
            elif "diện tích" in key_lc:
                if data['diện tích'] is None:
                    data['diện tích'] = keep_number(str(value))
                if data['giá/m2'] is None:
                    data['giá/m2'] = data['giá'] / data['diện tích']
            elif "phòng ngủ" in key_lc:
                if data['phòng ngủ'] is None:
                    data['phòng ngủ'] = keep_number(str(value))
            elif "pháp lý" in key_lc:
                data["pháp lý"] = handle_interior_text(value)
            elif "số tầng" in key_lc:
                data["số tầng"] = int(keep_number(str(value)))


    # --- 7) Mô tả ---
    desc_el = soup.select_one(".re__section-body.re__detail-content.js__section-body.js__pr-description.js__tracking")
    if desc_el:
        desc_text = _norm_text(desc_el.get_text("\n", strip=True))

        data_filtered = extract_text(desc_text.lower())
        if data_filtered['mặt tiền'] is not None:
            data['mặt tiền'] = data_filtered['mặt tiền']
        if data_filtered['phòng ngủ'] is not None:
            data['phòng ngủ'] = data_filtered['phòng ngủ']
        if data_filtered['pháp lý'] is not None:
            data['pháp lý'] = handle_interior_text(data_filtered['pháp lý'])
        if data_filtered['số tầng'] is not None:
            data['số tầng'] = data_filtered['số tầng']

    # --- 7) Tổng hợp ---


    return data


def get_property_details(links):
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
        futures = [executor.submit(get_page_source, link) for link in links]
        for future in concurrent.futures.as_completed(futures):
            try:
                future.result()
            except Exception as e:
                print(f"Error processing link: {e}")

if __name__ == "__main__":
    # Đọc các link từ file
    with open("linkNhaDat.txt", "r") as f:
        links = [line.strip() for line in f if line.strip()]
    
    # get_property_details(links[26050:26080])

    url = 'https://batdongsan.com.vn/ban-can-ho-chung-cu-duong-dien-bien-phu-phuong-22-vinhomes-central-park/ban-gap-2pn-87m-tai-gia-tot-nhat-thi-truong-pr43026593'
    get_page_source(url)
