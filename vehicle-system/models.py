from datetime import date
from typing import List
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import String, Integer, Date, Boolean, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from db import Base

# ------------------ SQLAlchemy Models ------------------

class Owner(Base):
    __tablename__ = "owners"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    national_id: Mapped[str] = mapped_column(String, unique=True, index=True)
    contact_number: Mapped[str] = mapped_column(String, nullable=False)
    address: Mapped[str] = mapped_column(String, nullable=False)

    vehicles: Mapped[List["Vehicle"]] = relationship(back_populates="owner")
    licenses: Mapped[List["License"]] = relationship(back_populates="owner")


class Vehicle(Base):
    __tablename__ = "vehicles"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    registration_number: Mapped[str] = mapped_column(String, unique=True, index=True)
    chassis_number: Mapped[str] = mapped_column(String, unique=True)
    model: Mapped[str] = mapped_column(String, nullable=False)
    registration_expiry: Mapped[date] = mapped_column(Date, nullable=False)

    owner_id: Mapped[int] = mapped_column(ForeignKey("owners.id"))

    owner: Mapped["Owner"] = relationship(back_populates="vehicles")
    licenses: Mapped[List["License"]] = relationship(back_populates="vehicle")


class License(Base):
    __tablename__ = "licenses"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    license_number: Mapped[str] = mapped_column(String, unique=True, index=True)
    license_class: Mapped[str] = mapped_column(String, nullable=False)
    issue_date: Mapped[date] = mapped_column(Date, nullable=False)
    expiry_date: Mapped[date] = mapped_column(Date, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True)

    owner_id: Mapped[int] = mapped_column(ForeignKey("owners.id"))
    vehicle_id: Mapped[int] = mapped_column(ForeignKey("vehicles.id"))

    owner: Mapped["Owner"] = relationship(back_populates="licenses")
    vehicle: Mapped["Vehicle"] = relationship(back_populates="licenses")


# ------------------ Pydantic Models ------------------

class VehicleCreate(BaseModel):
    registration_number: str = Field(..., example="KA01AB1234")
    chassis_number: str = Field(..., example="MH12AB1234CD56789")
    model: str = Field(..., example="Sedan")
    registration_expiry: date

    @field_validator("registration_expiry")
    def validate_expiry(cls, value: date):
        if value < date.today():
            raise ValueError("Registration expiry must be future date")
        return value


class OwnerCreate(BaseModel):
    name: str
    national_id: str
    contact_number: str
    address: str
    vehicle: VehicleCreate


class OwnerResponse(BaseModel):
    id: int
    name: str
    national_id: str
    contact_number: str
    address: str
    vehicle_id: int

    class Config:
        from_attributes = True


class LicenseCreate(BaseModel):
    owner_id: int
    vehicle_id: int
    license_number: str
    license_class: str
    issue_date: date
    expiry_date: date

    @field_validator("expiry_date")
    def validate_dates(cls, value, info):
        issue_date = info.data.get("issue_date")
        if issue_date and value <= issue_date:
            raise ValueError("Expiry must be after issue date")
        return value


class LicenseResponse(BaseModel):
    id: int
    license_number: str
    license_class: str
    issue_date: date
    expiry_date: date
    active: bool
    owner_id: int
    vehicle_id: int

    class Config:
        from_attributes = True


class ReminderResponse(BaseModel):
    owner_id: int
    vehicle_registration_number: str
    reminder_type: str
    due_date: date
    status: str
    message: str

    class Config:
        from_attributes = True
