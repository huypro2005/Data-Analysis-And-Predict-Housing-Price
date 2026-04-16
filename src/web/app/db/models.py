from datetime import datetime, timezone
from enum import Enum
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.database import Base


# ---------------------------------------------------------------------------
# Enums — map giữa mã số (model dùng) và tên tiếng Việt (hiển thị frontend)
# ---------------------------------------------------------------------------

class District(Enum):
    BINH_CHANH = (0,  'bình chánh')
    BINH_TAN   = (1,  'bình tân')
    BINH_THANH = (2,  'bình thạnh')
    CAN_GIO    = (3,  'cần giờ')
    CU_CHI     = (4,  'củ chi')
    GO_VAP     = (5,  'gò vấp')
    HOC_MON    = (6,  'hóc môn')
    NHA_BE     = (7,  'nhà bè')
    PHU_NHUAN  = (8,  'phú nhuận')
    QUAN_1     = (9,  'quận 1')
    QUAN_10    = (10, 'quận 10')
    QUAN_11    = (11, 'quận 11')
    QUAN_12    = (12, 'quận 12')
    QUAN_2     = (13, 'quận 2')
    QUAN_3     = (14, 'quận 3')
    QUAN_4     = (15, 'quận 4')
    QUAN_5     = (16, 'quận 5')
    QUAN_6     = (17, 'quận 6')
    QUAN_7     = (18, 'quận 7')
    QUAN_8     = (19, 'quận 8')
    QUAN_9     = (20, 'quận 9')
    THU_DUC    = (21, 'thủ đức')
    TAN_BINH   = (22, 'tân bình')
    TAN_PHU    = (23, 'tân phú')

    @property
    def code(self) -> int:
        return self.value[0]

    @property
    def label(self) -> str:
        return self.value[1]

    @classmethod
    def from_code(cls, code: int) -> "District":
        for member in cls:
            if member.code == code:
                return member
        raise ValueError(f"Không tìm thấy quận với mã {code}")

    @classmethod
    def from_label(cls, label: str) -> "District":
        label = label.strip().lower()
        for member in cls:
            if member.label == label:
                return member
        raise ValueError(f"Không tìm thấy quận '{label}'")


class RealEstateType(Enum):
    CAN_HO_CHUNG_CU = (0, 'căn hộ chung cư')
    NHA_RIENG       = (2, 'nhà riêng')
    NHA_BIET_THU    = (3, 'nhà biệt thự, liền kề')
    NHA_MAT_PHO     = (4, 'nhà mặt phố')
    BAN_DAT         = (7, 'bán đất')

    @property
    def code(self) -> int:
        return self.value[0]

    @property
    def label(self) -> str:
        return self.value[1]

    @classmethod
    def from_code(cls, code: int) -> "RealEstateType":
        for member in cls:
            if member.code == code:
                return member
        raise ValueError(f"Không tìm thấy loại BĐS với mã {code}")

    @classmethod
    def from_label(cls, label: str) -> "RealEstateType":
        label = label.strip().lower()
        for member in cls:
            if member.label == label:
                return member
        raise ValueError(f"Không tìm thấy loại BĐS '{label}'")


# ---------------------------------------------------------------------------
# ORM Models
# ---------------------------------------------------------------------------

class TrainingRun(Base):
    __tablename__ = "training_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    triggered_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    status: Mapped[str] = mapped_column(String(20))  # running | success | failed | skipped
    skip_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    total_rows: Mapped[int | None] = mapped_column(Integer, nullable=True)
    new_rows: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duration_sec: Mapped[float | None] = mapped_column(Float, nullable=True)
    model_replaced: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    model_path: Mapped[str | None] = mapped_column(Text, nullable=True)

    metrics: Mapped["ModelMetrics | None"] = relationship(
        "ModelMetrics", back_populates="run", uselist=False
    )
    feature_importances: Mapped[list["FeatureImportance"]] = relationship(
        "FeatureImportance", back_populates="run"
    )
    price_distributions: Mapped[list["PriceDistribution"]] = relationship(
        "PriceDistribution", back_populates="run"
    )
    district_price_stats: Mapped[list["DistrictPriceStats"]] = relationship(
        "DistrictPriceStats", back_populates="run"
    )
    activation: Mapped["PathActivation | None"] = relationship(
        "PathActivation", back_populates="run", uselist=False
    )


class ModelMetrics(Base):
    __tablename__ = "model_metrics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(Integer, ForeignKey("training_runs.id"), unique=True)
    rmse: Mapped[float] = mapped_column(Float)
    mae: Mapped[float] = mapped_column(Float)
    r2: Mapped[float] = mapped_column(Float)
    prev_rmse: Mapped[float | None] = mapped_column(Float, nullable=True)
    prev_mae: Mapped[float | None] = mapped_column(Float, nullable=True)
    prev_r2: Mapped[float | None] = mapped_column(Float, nullable=True)

    run: Mapped["TrainingRun"] = relationship("TrainingRun", back_populates="metrics")


class FeatureImportance(Base):
    __tablename__ = "feature_importances"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(Integer, ForeignKey("training_runs.id"))
    feature_name: Mapped[str] = mapped_column(String(100))
    importance: Mapped[float] = mapped_column(Float)

    run: Mapped["TrainingRun"] = relationship("TrainingRun", back_populates="feature_importances")


class PriceDistribution(Base):
    __tablename__ = "price_distributions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(Integer, ForeignKey("training_runs.id"))
    min_range: Mapped[float] = mapped_column(Float)   # giá/m² thấp nhất của bin (triệu)
    max_range: Mapped[float] = mapped_column(Float)   # giá/m² cao nhất của bin (triệu)
    price_range: Mapped[str] = mapped_column(String(50))  # label hiển thị, vd: "0-50 triệu"
    samples_count: Mapped[int] = mapped_column(Integer)

    run: Mapped["TrainingRun"] = relationship("TrainingRun", back_populates="price_distributions")


class DistrictPriceStats(Base):
    __tablename__ = "district_price_stats"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(Integer, ForeignKey("training_runs.id"))
    district_code: Mapped[int] = mapped_column(Integer)  # District.code
    property_code: Mapped[int] = mapped_column(Integer)  # RealEstateType.code
    median_price: Mapped[float] = mapped_column(Float)   # triệu VND/m²
    sample_count: Mapped[int] = mapped_column(Integer)   # lọc nhóm < 10 mẫu ở service layer

    __table_args__ = (
        Index("idx_district_property_run", "district_code", "property_code", "run_id", unique=True),
    )

    run: Mapped["TrainingRun"] = relationship("TrainingRun", back_populates="district_price_stats")

    @property
    def district(self) -> District:
        return District.from_code(self.district_code)

    @property
    def real_estate_type(self) -> RealEstateType:
        return RealEstateType.from_code(self.property_code)


class PathActivation(Base):
    """
    Lưu trạng thái active hiện tại của hệ thống.
    Chỉ được có đúng 1 record is_active=True tại mọi thời điểm.
    Service layer phải set is_active=False cho record cũ trước khi tạo record mới.

    run_id dùng làm version cho scatter:
      GET /eda/scatter/version → { run_id }
      Frontend so sánh → khác thì GET /eda/scatter/file
    """
    __tablename__ = "path_activation"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(Integer, ForeignKey("training_runs.id"), unique=True)
    path_model: Mapped[str] = mapped_column(String(200))    # đường dẫn file .pkl đang dùng
    path_scatter: Mapped[str] = mapped_column(String(200))  # đường dẫn file scatter CSV
    path_data: Mapped[str] = mapped_column(String(200))     # đường dẫn data.csv đã dùng để train
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, index=True)

    run: Mapped["TrainingRun"] = relationship("TrainingRun", back_populates="activation")
