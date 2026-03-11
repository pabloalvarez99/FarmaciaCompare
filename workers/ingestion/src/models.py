from datetime import datetime
from sqlalchemy import String, Boolean, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, mapped_column, Mapped, relationship
import uuid


class Base(DeclarativeBase):
    pass


class ActiveIngredient(Base):
    __tablename__ = "active_ingredients"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    isp_code: Mapped[str | None] = mapped_column(String, unique=True)
    atc_code: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    medications: Mapped[list["Medication"]] = relationship(back_populates="active_ingredient")


class Medication(Base):
    __tablename__ = "medications"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String, nullable=False)
    active_ingredient_id: Mapped[str | None] = mapped_column(ForeignKey("active_ingredients.id"))
    dosage: Mapped[str] = mapped_column(String, nullable=False)
    pharmaceutical_form: Mapped[str] = mapped_column(String, nullable=False)
    concentration: Mapped[str | None] = mapped_column(String)
    route_of_administration: Mapped[str | None] = mapped_column(String)
    prescription_required: Mapped[bool] = mapped_column(Boolean, default=False)
    isp_registration: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    active_ingredient: Mapped["ActiveIngredient | None"] = relationship(back_populates="medications")
    names: Mapped[list["MedicationName"]] = relationship(back_populates="medication", cascade="all, delete-orphan")


class MedicationName(Base):
    __tablename__ = "medication_names"
    __table_args__ = (UniqueConstraint("medication_id", "normalized_name"),)

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    medication_id: Mapped[str] = mapped_column(ForeignKey("medications.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String, nullable=False)
    name_type: Mapped[str] = mapped_column(String, nullable=False)
    laboratory: Mapped[str | None] = mapped_column(String)
    normalized_name: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    medication: Mapped["Medication"] = relationship(back_populates="names")
