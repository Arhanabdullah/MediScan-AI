from datetime import datetime, timezone

from sqlalchemy import Boolean, Float, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(default=utcnow)

    prescriptions: Mapped[list["Prescription"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class Prescription(Base):
    __tablename__ = "prescriptions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    filename: Mapped[str] = mapped_column(String(255))
    image_path: Mapped[str] = mapped_column(Text)
    raw_text: Mapped[str] = mapped_column(Text)
    ocr_engine: Mapped[str] = mapped_column(String(50))
    overall_confidence: Mapped[float] = mapped_column(Float)
    warnings: Mapped[list] = mapped_column(JSON, default=list)
    response_json: Mapped[dict] = mapped_column(JSON, default=dict)
    verified: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(default=utcnow, index=True)

    user: Mapped[User] = relationship(back_populates="prescriptions")
    detected_medicines: Mapped[list["DetectedMedicine"]] = relationship(
        back_populates="prescription", cascade="all, delete-orphan"
    )


class DetectedMedicine(Base):
    __tablename__ = "detected_medicines"

    id: Mapped[int] = mapped_column(primary_key=True)
    prescription_id: Mapped[str] = mapped_column(ForeignKey("prescriptions.id"), index=True)
    text: Mapped[str] = mapped_column(String(255))
    matched_name: Mapped[str] = mapped_column(String(255))
    generic_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    strength: Mapped[str | None] = mapped_column(String(100), nullable=True)
    form: Mapped[str | None] = mapped_column(String(100), nullable=True)
    frequency: Mapped[str | None] = mapped_column(String(100), nullable=True)
    match_score: Mapped[float] = mapped_column(Float)
    confidence: Mapped[float] = mapped_column(Float)
    confirmed: Mapped[bool] = mapped_column(Boolean, default=False)

    prescription: Mapped[Prescription] = relationship(back_populates="detected_medicines")
