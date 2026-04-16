import os
import time
from datetime import datetime, timezone
from app.config import API_PARTNER

import joblib as jb

from app.config import BASE_DIR
from app.db.models import (
    DistrictPriceStats,
    FeatureImportance,
    ModelMetrics,
    PathActivation,
    PriceDistribution,
    TrainingRun,
)
from app.retrain.retrain import RetrainService

# Ánh xạ label bin → (min_range, max_range)
_BIN_RANGES = {
    "0-30":    (0.0,   30.0),
    "30-50":   (30.0,  50.0),
    "50-70":   (50.0,  70.0),
    "70-90":   (70.0,  90.0),
    "90-110":  (90.0,  110.0),
    "110-130": (110.0, 130.0),
    "130+":    (130.0, 9999.0),
}



class RetrainOrchestrator:
    def __init__(self, db_session):
        self.db = db_session

    def request_data_from_partner(self) -> str:
        """
        Gọi API partner để lấy data path mới.
        Trả về data_path (str) hoặc raise exception nếu lỗi.
        """
        import requests

        try:
            activation = (
                self.db.query(PathActivation)
                .filter(PathActivation.is_active == True)
                .first()
            )
            training_run = activation.run if activation else None
            url_partner = f'{API_PARTNER}?tab=ban&province=1&start_post={training_run.triggered_at.isoformat()}' if training_run else API_PARTNER
        except Exception as exc:
            raise RuntimeError(f"Failed to fetch training run: {exc}") from exc
        try:
            response = requests.get(url_partner, timeout=30)
            response.raise_for_status()
            data = response.json()
            return data
        except Exception as exc:
            raise RuntimeError(f"Failed to fetch data from partner: {exc}") from exc

    # ------------------------------------------------------------------
    def check_new_rows(self, data_path: str) -> int:
        """
        Lấy data mới từ partner.
        - Nếu count < 100: không ghi file, trả về count để run() skip.
        - Nếu count >= 100: append vào data_path, trả về count.
        """
        import os
        import pandas as pd

        try:
            data_partner = self.request_data_from_partner()
        except Exception as exc:
            print(f"Error requesting data from partner: {exc}")
            return 0

        count = data_partner.get('count', 0)
        if count < 100:
            return count

        # Partner: coord_x = longitude (106.xxx), coord_y = latitude (10.xxx).
        # CSV lưu tọa độ * 1e9 — retrain.py chia lại khi load.
        # tọa độ x = latitude → coord_y * 1e9
        # tọa độ y = longitude → coord_x * 1e9
        CSV_COLUMNS = [
            'loại nhà đất', 'địa chỉ', 'giá', 'diện tích', 'giá/m2',
            'mặt tiền', 'phòng ngủ', 'pháp lý', 'tọa độ x', 'tọa độ y', 'số tầng',
        ]
        try:
            rows = []
            for item in data_partner['data']:
                lat = float(item.get('coord_y') or 0) * 1e9  # coord_y = latitude
                lon = float(item.get('coord_x') or 0) * 1e9  # coord_x = longitude
                rows.append([
                    item.get('property_type', ''),
                    item.get('district', ''),
                    item.get('price', ''),
                    item.get('area_m2', ''),
                    item.get('price_per_m2', ''),
                    item.get('frontage', ''),
                    item.get('bedrooms', ''),
                    item.get('legal_status', ''),
                    lat,
                    lon,
                    item.get('floors', ''),
                ])

            new_df = pd.DataFrame(rows, columns=CSV_COLUMNS)
            write_header = not os.path.exists(data_path) or os.path.getsize(data_path) == 0
            new_df.to_csv(data_path, mode='a', header=write_header, index=False)

            return count
        except KeyError:
            raise ValueError("Invalid data format from partner")

    # ------------------------------------------------------------------
    def run(self, data_path: str) -> dict:
        import pandas as pd

        start_time = time.time()
        run = None

        try:
            # 1. Check new rows
            new_rows = self.check_new_rows(data_path)
            import pandas as _pd
            total_rows = len(_pd.read_csv(data_path))

            if new_rows < 100:
                run = TrainingRun(
                    status="skipped",
                    skip_reason=f"Chỉ có {new_rows} dòng mới (cần ≥ 100)",
                    total_rows=total_rows,
                    new_rows=new_rows,
                )
                self.db.add(run)
                self.db.commit()
                return {"status": "skipped", "new_rows": new_rows}

            # 2. Tạo run record
            run = TrainingRun(status="running", total_rows=total_rows, new_rows=new_rows)
            self.db.add(run)
            self.db.commit()
            self.db.refresh(run)

            # 3. Train
            retrain = RetrainService(data_path, self.db)
            result = retrain.retrain_model()

            pipeline = result["pipeline"]
            rmse = result["rmse"]
            mae = result["mae"]
            r2 = result["r2"]

            # 4. Load model cũ để so sánh
            prev_rmse = prev_mae = prev_r2 = None
            old_activation = (
                self.db.query(PathActivation)
                .filter(PathActivation.is_active == True)  # noqa: E712
                .first()
            )
            if old_activation:
                try:
                    old_pipeline = jb.load(str(BASE_DIR / old_activation.path_model))
                    prev_rmse = old_activation.run.metrics.rmse if old_activation.run and old_activation.run.metrics else None
                    prev_mae  = old_activation.run.metrics.mae  if old_activation.run and old_activation.run.metrics else None
                    prev_r2   = old_activation.run.metrics.r2   if old_activation.run and old_activation.run.metrics else None
                except Exception:
                    old_activation = None

            # 5. Quyết định replace model
            model_replaced = False
            if old_activation is None or prev_rmse is None or rmse < prev_rmse:
                # Lưu model .pkl
                model_dir = BASE_DIR / "media" / "model_ai"
                model_dir.mkdir(parents=True, exist_ok=True)
                timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
                model_filename = f"rf_{timestamp}.pkl"
                model_abs = model_dir / model_filename
                jb.dump(pipeline, str(model_abs))

                # Lưu scatter CSV (sample 2000)
                scatter_dir = BASE_DIR / "media" / "scatter"
                scatter_dir.mkdir(parents=True, exist_ok=True)
                scatter_filename = f"scatter_{timestamp}.csv"
                scatter_abs = scatter_dir / scatter_filename
                scatter_df = result["data_scatter_plot"]
                if len(scatter_df) > 2000:
                    scatter_df = scatter_df.sample(2000, random_state=42)
                scatter_df.to_csv(str(scatter_abs), index=False)

                # Deactivate tất cả record cũ trong cùng 1 transaction
                self.db.query(PathActivation).filter(
                    PathActivation.is_active == True  # noqa: E712
                ).update({"is_active": False})

                new_activation = PathActivation(
                    run_id=run.id,
                    path_model=str(model_dir.relative_to(BASE_DIR) / model_filename),
                    path_scatter=str(scatter_dir.relative_to(BASE_DIR) / scatter_filename),
                    path_data=str(os.path.relpath(data_path, str(BASE_DIR))),
                    is_active=True,
                )
                self.db.add(new_activation)
                model_replaced = True

            # 6. Lưu ModelMetrics
            metrics = ModelMetrics(
                run_id=run.id,
                rmse=rmse,
                mae=mae,
                r2=r2,
                prev_rmse=prev_rmse,
                prev_mae=prev_mae,
                prev_r2=prev_r2,
            )
            self.db.add(metrics)

            # 7. Lưu FeatureImportance
            for feat_name, importance in result["importance"].items():
                self.db.add(FeatureImportance(
                    run_id=run.id,
                    feature_name=feat_name,
                    importance=float(importance),
                ))

            # 8. Lưu PriceDistribution
            for label, count in result["data_price_distribution"].items():
                min_r, max_r = _BIN_RANGES.get(label, (0.0, 0.0))
                self.db.add(PriceDistribution(
                    run_id=run.id,
                    min_range=min_r,
                    max_range=max_r,
                    price_range=label,
                    samples_count=int(count),
                ))

            # 9. Lưu DistrictPriceStats
            for _, row in result["data_district_stats"].iterrows():
                self.db.add(DistrictPriceStats(
                    run_id=run.id,
                    district_code=int(row["district_code"]),
                    property_code=int(row["property_code"]),
                    median_price=float(row["median_price"]),
                    sample_count=int(row["sample_count"]),
                ))

            # 10. Update TrainingRun
            duration = time.time() - start_time
            run.status = "success"
            run.duration_sec = duration
            run.model_replaced = model_replaced
            self.db.commit()

            return {
                "status": "success",
                "run_id": run.id,
                "rmse": rmse,
                "mae": mae,
                "r2": r2,
                "model_replaced": model_replaced,
                "new_rows": new_rows,
                "total_rows": total_rows,
            }

        except Exception as exc:
            if run is not None:
                try:
                    self.db.rollback()
                    run.status = "failed"
                    run.duration_sec = time.time() - start_time
                    self.db.commit()
                except Exception:
                    pass
            raise exc
