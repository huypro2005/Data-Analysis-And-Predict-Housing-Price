import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.neighbors import KNeighborsRegressor
from xgboost import XGBRegressor
from sklearn.metrics import mean_absolute_error, r2_score
import joblib as jl

# Load dữ liệu
df = pd.read_csv('./data_1.dedup.csv')  # hoặc từ chuỗi trên

# Chuyển 'X' → NaN
df.replace('X', np.nan, inplace=True)

# Chuyển các cột số sang float
cols = ['loại nhà đất', 'địa chỉ', 'giá', 'diện tích', 'giá/m2', 'mặt tiền',
       'phòng ngủ', 'pháp lý', 'tọa độ x', 'tọa độ y', 'số tầng']
df[cols] = df[cols].astype(float)

# Drop cột 'giá'
df = df.drop(columns=['giá'])

# Drop dòng nếu thiếu giá/m2 (target)
df = df.dropna(subset=['giá/m2'])

df.loc[df['loại nhà đất'] == 7, 'phòng ngủ'] = 0
df.loc[df['loại nhà đất'] == 7, 'số tầng'] = 0

df.loc[df['loại nhà đất'] == 6, 'phòng ngủ'] = 0
df.loc[df['loại nhà đất'] == 6, 'số tầng'] = 0

df.loc[df['loại nhà đất'] == 9, 'phòng ngủ'] = 0
df.loc[df['loại nhà đất'] == 9, 'số tầng'] = 0



df.loc[df['loại nhà đất'] == 0, 'mặt tiền'] = 0
df.loc[df['loại nhà đất'] == 0, 'số tầng'] = 0




# Gán trung bình hoặc giá trị đặc biệt cho missing feature
df['mặt tiền'].fillna(0, inplace=True)
df['phòng ngủ'].fillna(0, inplace=True)
df['pháp lý'].fillna(0, inplace=True)
df['số tầng'].fillna(0, inplace=True)

X = df.drop(columns=['giá/m2'])
y = df['giá/m2']

X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

models = [
    LinearRegression(),
    KNeighborsRegressor(n_neighbors=5),
    XGBRegressor(n_estimators=100, random_state=42)
]

# model = RandomForestRegressor(n_estimators=100, random_state=42)
def train_model(model, idx=0):
    model.fit(X_train, y_train)


    y_pred = model.predict(X_test)

    mae = mean_absolute_error(y_test, y_pred)
    r2 = r2_score(y_test, y_pred)

    print(f"MAE: {mae:.2f}")
    print(f"R2: {r2:.2f}")

    try:
        jl.dump(model, f'model_{idx}.pkl')
    except Exception as e:
        print(f"Error saving model: {e}")
    # test model
    test_data = pd.DataFrame({
        'loại nhà đất': [4],
        'địa chỉ': [23],
        'diện tích': [75],
        'mặt tiền': [5],
        'phòng ngủ': [4],
        'pháp lý': [1],
        'tọa độ x': [10.7795105160091 * 1000000000],
        'tọa độ y': [106.624395422216 * 1000000000],
        'số tầng': [4]
    })
    # 10.7795105160091,106.624395422216
    model1 = jl.load(f'model_{idx}.pkl')
    predicted_price_per_m2 = model1.predict(test_data)
    print(f"Giá dự đoán cho nhà đất: {predicted_price_per_m2[0]:.5f} triệu/m2")
    print(f"Giá dự đoán cho nhà đất: {predicted_price_per_m2[0] * test_data['diện tích'][0]:.5f} triệu")

if __name__ == "__main__":
    # for idx, model in enumerate(models):
    #     print(f"Training {model.__class__.__name__}...")
    #     train_model(model, idx=idx)
    
    # test model
    test_data = pd.DataFrame({
        'loại nhà đất': [4],
        'địa chỉ': [23],
        'diện tích': [75],
        'mặt tiền': [5],
        'phòng ngủ': [4],
        'pháp lý': [1],
        'tọa độ x': [10.7795105160091 * 1000000000],
        'tọa độ y': [106.624395422216 * 1000000000],
        'số tầng': [4]
    })
    # 10.7795105160091,106.624395422216
    model1 = jl.load(f'model1.pkl')
    predicted_price_per_m2 = model1.predict(test_data)
    print(f"Giá dự đoán cho nhà đất: {predicted_price_per_m2[0]:.5f} triệu/m2")
    print(f"Giá dự đoán cho nhà đất: {predicted_price_per_m2[0] * test_data['diện tích'][0]:.5f} triệu")