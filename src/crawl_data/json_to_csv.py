import csv, json



with open('data.json', 'r', encoding='utf-8') as f:
    data = f.readlines()

for i, line in enumerate(data):
    try:
        data[i] = json.loads(line)
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON on line {i}: {e}")
        data[i] = {}

print(type(data))
a = ['loại nhà đất', 'địa chỉ', 'giá', 'diện tích', 'giá/m2', 'mặt tiền', 'phòng ngủ', 'pháp lý', 'tọa độ x', 'tọa độ y', 'số tầng']

with open('data_test1.csv', 'a', newline='', encoding='utf-8') as f:
    writer = csv.DictWriter(f, fieldnames=a)
    # writer.writeheader()
    writer.writerows(data)

