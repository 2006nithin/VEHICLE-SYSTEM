from datetime import date
from typing import Optional
from pydantic import BaseModel, Field, validator
from sqlalchemy import Boolean, Column, Date, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, relationship
from db import Base

class Owner(Base):
    __tablename__ = "owners"

    id: Mapped[int] = Column(Integer, primary_key=True, index=True)
    name: Mapped[str] = Column(String, nullable=False)
    national_id: Mapped[str] = Column(String, unique=True, nullable=False, index=True)
    contact_number: Mapped[str] = Column(String, nullable=False)
    address: Mapped[str] = Column(String, nullable=False)

    vehicles = relationship("Vehicle", back_populates="owner")
    licenses = relationship("License", back_populates="owner")

class Vehicle(Base):
    __tablename__ = "vehicles"

    id: Mapped[int] = Column(Integer, primary_key=True, index=True)
    registration_number: Mapped[str] = Column(String, unique=True, nullable=False, index=True)
    chassis_number: Mapped[str] = Column(String, unique=True, nullable=False)
    model: Mapped[str] = Column(String, nullable=False)
    registration_expiry: Mapped[date] = Column(Date, nullable=False)
    owner_id: Mapped[int] = Column(Integer, ForeignKey("owners.id"), nullable=False)

    owner = relationship("Owner", back_populates="vehicles")
    licenses = relationship("License", back_populates="vehicle")

class License(Base):
    __tablename__ = "licenses"

    id: Mapped[int] = Column(Integer, primary_key=True, index=True)
    license_number: Mapped[str] = Column(String, unique=True, nullable=False, index=True)
    license_class: Mapped[str] = Column(String, nullable=False)
    issue_date: Mapped[date] = Column(Date, nullable=False)
    expiry_date: Mapped[date] = Column(Date, nullable=False)
    active: Mapped[bool] = Column(Boolean, default=True)
    owner_id: Mapped[int] = Column(Integer, ForeignKey("owners.id"), nullable=False)
    vehicle_id: Mapped[int] = Column(Integer, ForeignKey("vehicles.id"), nullable=False)

    owner = relationship("Owner", back_populates="licenses")
    vehicle = relationship("Vehicle", back_populates="licenses")

class VehicleCreate(BaseModel):
    registration_number: str = Field(..., example="KA01AB1234")
    chassis_number: str = Field(..., example="MH12AB1234CD56789")
    model: str = Field(..., example="Sedan")
    registration_expiry: date

    @validator("registration_expiry")
    def registration_expiry_must_be_future(cls, value: date) -> date:
        if value < date.today():
            raise ValueError("Vehicle registration expiry must be a future date")
        return value

class OwnerCreate(BaseModel):
    name: str = Field(..., example="Rahul Sharma")
    national_id: str = Field(..., example="A123456789")
    contact_number: str = Field(..., example="+919876543210")
    address: str = Field(..., example="123 Main Road, Bangalore")
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
    license_number: str = Field(..., example="DL-1234567890123")
    license_class: str = Field(..., example="LMV")
    issue_date: date
    expiry_date: date

    @validator("expiry_date")
    def expiry_must_be_after_issue(cls, value: date, values: dict) -> date:
        if "issue_date" in values and value <= values["issue_date"]:
            raise ValueError("Expiry date must come after issue date")
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
