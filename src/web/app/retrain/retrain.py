import pandas as pd
import numpy as np
from sklearn.model_selection import StratifiedShuffleSplit
from sklearn.ensemble import RandomForestRegressor
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from sklearn.metrics import mean_absolute_error, r2_score, mean_squared_error
import joblib as jb

REAL_ESTATE_ = {
    'căn hộ chung cư': 0,
    'chung cư mini, căn hộ dịch vụ': 1,  # X — bị loại
    'nhà riêng': 2,
    'nhà biệt thự, liền kề': 3,
    'nhà mặt phố': 4,
    'shophouse, nhà phố thương mại': 5,   # X — bị loại
    'đất nền dự án': 6,                   # X — bị loại
    'bán đất': 7,
    'condotel': 8,                        # X — bị loại
    'kho nhà xưởng': 9                    # X — bị loại
}

ADDRESS_VAL = {
    0: 'bình chánh',  1: 'bình tân',    2: 'bình thạnh',
    3: 'cần giờ',     4: 'củ chi',      5: 'gò vấp',
    6: 'hóc môn',     7: 'nhà bè',      8: 'phú nhuận',
    9: 'quận 1',      10: 'quận 10',    11: 'quận 11',
    12: 'quận 12',    13: 'quận 2',     14: 'quận 3',
    15: 'quận 4',     16: 'quận 5',     17: 'quận 6',
    18: 'quận 7',     19: 'quận 8',     20: 'quận 9',
    21: 'thủ đức',    22: 'tân bình',   23: 'tân phú',
}

REAL_ESTATE_VAL = {v: k for k, v in REAL_ESTATE_.items()}

# Tọa độ trung tâm TP.HCM (Nhà thờ Đức Bà)
HCM_LAT = 10.7769
HCM_LON = 106.7009


def haversine(lat1, lon1, lat2=HCM_LAT, lon2=HCM_LON):
    R = 6371
    lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
    dlat, dlon = lat2 - lat1, lon2 - lon1
    a = np.sin(dlat / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2) ** 2
    return R * 2 * np.arcsin(np.sqrt(a))


class RetrainService:
    def __init__(self, file_path: str, db_session):
        self.db_session = db_session
        self.df = pd.read_csv(file_path)

        # Tọa độ trong data.csv được lưu dạng scale ×10⁹ → chuẩn hóa về độ thực
        self.df["tọa độ x"] = self.df["tọa độ x"] / 1e9
        self.df["tọa độ y"] = self.df["tọa độ y"] / 1e9

        self.df["cách trung tâm"] = haversine(self.df["tọa độ x"], self.df["tọa độ y"])

        # Bỏ cột giá tuyệt đối để tránh data leakage
        self.df.drop(columns=["giá"], inplace=True)

    def __preprocess_data(self):
        # 1. Loại bỏ trùng lặp
        self.df.drop_duplicates(inplace=True)

        # 2. Loại bỏ loại BĐS ít dữ liệu / không hỗ trợ
        remove_types = {
            REAL_ESTATE_["chung cư mini, căn hộ dịch vụ"],
            REAL_ESTATE_["shophouse, nhà phố thương mại"],
            REAL_ESTATE_["đất nền dự án"],
            REAL_ESTATE_["condotel"],
            REAL_ESTATE_["kho nhà xưởng"],
        }
        self.df = self.df[~self.df["loại nhà đất"].isin(remove_types)]

        # 3. Loại bỏ dữ liệu ngoài phạm vi TP.HCM (tọa độ đã chuẩn hóa về độ thực)
        self.df = self.df[
            self.df["tọa độ x"].between(10.38, 11.10) &
            self.df["tọa độ y"].between(106.1, 106.8)
        ]

        # 4. Loại bỏ dữ liệu pháp lý không hợp lệ
        self.df = self.df[self.df["pháp lý"] != 2]
        self.df = self.df[self.df["pháp lý"].notna()]
        self.df.drop(columns=["pháp lý"], inplace=True)

        # 5. Lọc outlier trên toàn bộ df TRƯỚC khi split
        self.df = self.df[self.df["phòng ngủ"] < 11]
        self.df = self.df[self.df["mặt tiền"] <= 30]
        self.df = self.df[self.df["giá/m2"] <= 500]
        self.df = self.df[self.df["diện tích"].between(15, 500)]
        self.df = self.df.reset_index(drop=True)

        # 6. Tính dữ liệu cho biểu đồ (sau khi đã clean hoàn toàn)
        data_price_distribution = self.__compute_price_distribution()
        data_scatter_plot = self.df[["tọa độ x", "tọa độ y", "diện tích", "giá/m2"]].copy()
        data_district_stats = self.__compute_district_stats()

        # 7. Split train/test
        self.train_set, self.test_set = self.__split_data()

        # 8. Fill median từ train_set, áp dụng cho cả hai (tránh data leakage từ test)
        for col in ["mặt tiền", "phòng ngủ", "số tầng"]:
            median_val = self.train_set[col].median()
            self.train_set = self.train_set.copy()
            self.test_set = self.test_set.copy()
            self.train_set[col] = self.train_set[col].fillna(median_val)
            self.test_set[col] = self.test_set[col].fillna(median_val)

        return data_price_distribution, data_scatter_plot, data_district_stats

    def __compute_price_distribution(self) -> dict:
        bins = [0., 30., 50., 70., 90., 110., 130., np.inf]
        labels = ["0-30", "30-50", "50-70", "70-90", "90-110", "110-130", "130+"]
        cats = pd.cut(self.df["giá/m2"], bins=bins, labels=labels)
        return cats.value_counts().reindex(labels, fill_value=0).to_dict()

    def __compute_district_stats(self) -> pd.DataFrame:
        stats = (
            self.df.groupby(["địa chỉ", "loại nhà đất"])["giá/m2"]
            .agg(median_price="median", sample_count="count")
            .reset_index()
            .rename(columns={"địa chỉ": "district_code", "loại nhà đất": "property_code"})
        )
        # Loại nhóm < 10 mẫu để tránh giá trị không ổn định
        return stats[stats["sample_count"] >= 10].reset_index(drop=True)

    def __split_data(self):
        df = self.df.copy()
        df["distance_center_cat"] = pd.cut(
            df["cách trung tâm"],
            bins=[0., 5., 10., 15., np.inf],
            labels=[1, 2, 3, 4]
        )
        splitter = StratifiedShuffleSplit(n_splits=1, test_size=0.2, random_state=42)
        train_idx, test_idx = next(splitter.split(df, df["distance_center_cat"]))
        train_set = df.iloc[train_idx].drop(columns=["distance_center_cat"]).reset_index(drop=True)
        test_set = df.iloc[test_idx].drop(columns=["distance_center_cat"]).reset_index(drop=True)
        return train_set, test_set

    def __evaluate(self, pipeline, X_test: pd.DataFrame, y_test: pd.Series) -> tuple:
        # Dùng pipeline (không phải raw model) để X_test được impute trước khi predict
        pred = pipeline.predict(X_test)
        rmse = float(np.sqrt(mean_squared_error(y_test, pred)))
        mae = float(mean_absolute_error(y_test, pred))
        r2 = float(r2_score(y_test, pred))
        return rmse, mae, r2

    def retrain_model(self) -> dict:
        data_price_distribution, data_scatter_plot, data_district_stats = self.__preprocess_data()

        X_train = self.train_set.drop(columns=["giá/m2"])
        y_train = np.log(self.train_set["giá/m2"])
        X_test = self.test_set.drop(columns=["giá/m2"])
        y_test = np.log(self.test_set["giá/m2"])

        pipeline = Pipeline([
            ("imputer", SimpleImputer(strategy="median")),
            ("model", RandomForestRegressor(
                n_estimators=300,
                max_depth=30,
                min_samples_split=2,
                min_samples_leaf=1,
                random_state=42,
            ))
        ])
        pipeline.fit(X_train, y_train)

        rf_model = pipeline.named_steps["model"]
        importance = pd.Series(
            rf_model.feature_importances_,
            index=X_train.columns
        ).sort_values(ascending=False)

        rmse, mae, r2 = self.__evaluate(pipeline, X_test, y_test)

        return {
            "pipeline": pipeline,
            "importance": importance,
            "data_price_distribution": data_price_distribution,
            "data_scatter_plot": data_scatter_plot,
            "data_district_stats": data_district_stats,
            "rmse": rmse,
            "mae": mae,
            "r2": r2,
        }
