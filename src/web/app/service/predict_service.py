import os
import joblib as jl
from app.config import BASE_DIR
import numpy as np
import pandas as pd

model_path = os.path.join(BASE_DIR, 'model_ai/RandomForestRegressor.pkl')
pipeline = jl.load(model_path)
median = pipeline.named_steps['imputer'].statistics_
model = pipeline.named_steps['model']
X_train_columns = ['loại nhà đất', 'địa chỉ', 'diện tích', 'mặt tiền', 'phòng ngủ',
       'tọa độ x', 'tọa độ y', 'số tầng', 'distance_center_km']
median_series = pd.Series(median, index=X_train_columns)

# tọa độ trung tâm thành phố Hồ Chí Minh (Nhà thờ Đức Bà)
lat = 10.7769
lon = 106.7009


def predict(data: dict):
    try:
        data_processed = handle_input(data)
        prediction_price_per_m2 = np.exp(model.predict(data_processed))
        return prediction_price_per_m2[0], prediction_price_per_m2[0] * data_processed['diện tích'][0]
    except Exception as e:
        print(f"Error occurred: {e}")
        return None, None


def handle_input(input_data: dict):
    data = pd.DataFrame({
                'loại nhà đất': [int(input_data['loại nhà đất'])],
                'địa chỉ': [int(input_data['địa chỉ'])],
                'diện tích': [float(input_data['diện tích'])],
                'mặt tiền': [float(input_data['mặt tiền']) if input_data['mặt tiền'] is not None else np.nan],
                'phòng ngủ': [int(input_data['phòng ngủ']) if input_data['phòng ngủ'] is not None else np.nan],
                'tọa độ x': [float(input_data['tọa độ x'])],
                'tọa độ y': [float(input_data['tọa độ y'])],
                'số tầng': [int(input_data['số tầng']) if input_data['số tầng'] is not None else np.nan]
            })
    data["distance_center_km"] = haversine(
                                    data["tọa độ x"],
                                    data["tọa độ y"],
                                    lat,
                                    lon
                                )

    data.fillna(median_series, inplace=True)
    return data


def haversine(lat1, lon1, lat2 = lat, lon2 = lon):
    R = 6371

    lat1, lon1, lat2, lon2 = map(
        np.radians, [lat1, lon1, lat2, lon2]
    )

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = np.sin(dlat/2)**2 + \
        np.cos(lat1)*np.cos(lat2)*np.sin(dlon/2)**2

    c = 2*np.arcsin(np.sqrt(a))

    return R*c