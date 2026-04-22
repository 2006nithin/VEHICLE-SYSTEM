from datetime import date
import logging
from pathlib import Path
from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from db import Base, engine, SessionLocal
from mongo_client import insert_reminder, find_reminders
from models import Owner, Vehicle, License, OwnerCreate, OwnerResponse, LicenseCreate, LicenseResponse

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

Base.metadata.create_all(bind=engine)

logger = logging.getLogger("vehicle_system")

app = FastAPI(
    title="Vehicle Registration and License Issuance System",
    description="Stores owners and vehicles in a relational DBMS and keeps renewal reminders in MongoDB.",
)

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def raise_duplicate(message: str):
    raise HTTPException(status_code=400, detail=message)


@app.get("/", response_class=HTMLResponse)
def read_root():
    html_file = STATIC_DIR / "index.html"
    return HTMLResponse(html_file.read_text(encoding="utf-8"))


def validate_vehicle_registration(vehicle: Vehicle):
    if vehicle.registration_expiry < date.today():
        raise HTTPException(status_code=400, detail="Vehicle registration has expired.")


def create_reminder(owner_id: int, registration_number: str, due_date: date, reminder_type: str, message: str):
    reminder = {
        "owner_id": owner_id,
        "vehicle_registration_number": registration_number,
        "reminder_type": reminder_type,
        "due_date": due_date,
        "status": "pending",
        "message": message,
    }
    try:
        return insert_reminder(reminder)
    except RuntimeError as error:
        logger.warning("Reminder storage unavailable: %s", error)
        return None


@app.post("/owners/register", response_model=OwnerResponse)
def register_owner(payload: OwnerCreate, db: Session = Depends(get_db)):
    existing_owner = db.query(Owner).filter(Owner.national_id == payload.national_id).first()
    if existing_owner:
        raise_duplicate("Owner with this national ID already exists.")

    existing_vehicle = db.query(Vehicle).filter(
        (Vehicle.registration_number == payload.vehicle.registration_number)
        | (Vehicle.chassis_number == payload.vehicle.chassis_number)
    ).first()

    if existing_vehicle:
        raise_duplicate("Vehicle with this registration number or chassis number already exists.")

    owner = Owner(
        name=payload.name,
        national_id=payload.national_id,
        contact_number=payload.contact_number,
        address=payload.address,
    )
    db.add(owner)
    db.commit()
    db.refresh(owner)

    vehicle = Vehicle(
        registration_number=payload.vehicle.registration_number,
        chassis_number=payload.vehicle.chassis_number,
        model=payload.vehicle.model,
        registration_expiry=payload.vehicle.registration_expiry,
        owner_id=owner.id,
    )
    db.add(vehicle)
    db.commit()
    db.refresh(vehicle)

    return OwnerResponse(
        id=owner.id,
        name=owner.name,
        national_id=owner.national_id,
        contact_number=owner.contact_number,
        address=owner.address,
        vehicle_id=vehicle.id,
    )


@app.post("/licenses/issue", response_model=LicenseResponse)
def issue_license(payload: LicenseCreate, db: Session = Depends(get_db)):
    owner = db.query(Owner).filter(Owner.id == payload.owner_id).first()
    if not owner:
        raise HTTPException(status_code=404, detail="Owner not found.")

    vehicle = db.query(Vehicle).filter(Vehicle.id == payload.vehicle_id, Vehicle.owner_id == owner.id).first()
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found for the given owner.")

    validate_vehicle_registration(vehicle)

    duplicate_license = db.query(License).filter(License.license_number == payload.license_number).first()
    if duplicate_license:
        raise_duplicate("A license with this license number already exists.")

    active_license = db.query(License).filter(
        License.owner_id == owner.id,
        License.vehicle_id == vehicle.id,
        License.active == True,
        License.expiry_date >= date.today(),
    ).first()
    if active_license:
        raise_duplicate("An active license already exists for this owner and vehicle.")

    license_record = License(
        license_number=payload.license_number,
        license_class=payload.license_class,
        issue_date=payload.issue_date,
        expiry_date=payload.expiry_date,
        active=payload.expiry_date >= date.today(),
        owner_id=owner.id,
        vehicle_id=vehicle.id,
    )
    db.add(license_record)
    db.commit()
    db.refresh(license_record)

    create_reminder(
        owner_id=owner.id,
        registration_number=vehicle.registration_number,
        due_date=payload.expiry_date,
        reminder_type="license_renewal",
        message=f"License {payload.license_number} expires on {payload.expiry_date}",
    )

    return license_record


@app.post("/licenses/{license_id}/renew", response_model=LicenseResponse)
def renew_license(license_id: int, payload: LicenseCreate, db: Session = Depends(get_db)):
    existing = db.query(License).filter(License.id == license_id).first()
    if not existing:
        raise HTTPException(status_code=404, detail="License not found.")

    if payload.owner_id != existing.owner_id or payload.vehicle_id != existing.vehicle_id:
        raise HTTPException(status_code=400, detail="Owner and vehicle must match the existing license.")

    if payload.expiry_date <= existing.expiry_date:
        raise HTTPException(status_code=400, detail="A renewal expiry must be later than the current expiry.")

    existing.active = payload.expiry_date >= date.today()
    existing.issue_date = payload.issue_date
    existing.expiry_date = payload.expiry_date
    existing.license_number = payload.license_number
    existing.license_class = payload.license_class
    db.commit()
    db.refresh(existing)

    create_reminder(
        owner_id=existing.owner_id,
        registration_number=existing.vehicle.registration_number,
        due_date=payload.expiry_date,
        reminder_type="license_renewal",
        message=f"License renewed until {payload.expiry_date}",
    )

    return existing


@app.get("/licenses/{license_id}", response_model=LicenseResponse)
def get_license(license_id: int, db: Session = Depends(get_db)):
    record = db.query(License).filter(License.id == license_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="License not found.")
    if record.expiry_date < date.today():
        raise HTTPException(status_code=400, detail="License document has expired.")
    return record


@app.get("/reminders")
def list_reminders():
    try:
        return find_reminders()
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail="Reminder service unavailable")


# Dashboard Endpoints
@app.get("/dashboard/stats")
def get_dashboard_stats(db: Session = Depends(get_db)):
    """Get dashboard statistics"""
    total_registrations = db.query(Owner).count()
    
    active_vehicles = db.query(Vehicle).filter(Vehicle.registration_expiry >= date.today()).count()
    
    # Expiring licenses (within 14 days)
    from datetime import timedelta
    fourteen_days_from_now = date.today() + timedelta(days=14)
    expiring_licenses = db.query(License).filter(
        License.expiry_date >= date.today(),
        License.expiry_date <= fourteen_days_from_now
    ).count()
    
    expired_documents = db.query(License).filter(License.expiry_date < date.today()).count()
    
    return {
        "total_registrations": total_registrations,
        "active_vehicles": active_vehicles,
        "expiring_licenses": expiring_licenses,
        "expired_documents": expired_documents,
    }


@app.get("/dashboard/alerts")
def get_dashboard_alerts(db: Session = Depends(get_db)):
    """Get dashboard alerts"""
    expired_vehicles = db.query(Vehicle).filter(Vehicle.registration_expiry < date.today()).count()
    
    alert_message = None
    if expired_vehicles > 0:
        alert_message = f"⚠️ Attention: {expired_vehicles} vehicle(s) have expired registration. Renewal action required"
    
    return {
        "alert_message": alert_message,
    }


@app.get("/dashboard/recent-vehicles")
def get_recent_vehicles(db: Session = Depends(get_db)):
    """Get recent vehicle registrations for dashboard table"""
    # Get the 5 most recent vehicles
    recent_vehicles = db.query(Vehicle, Owner).join(
        Owner, Vehicle.owner_id == Owner.id
    ).order_by(Vehicle.id.desc()).limit(5).all()
    
    vehicles_data = []
    for vehicle, owner in recent_vehicles:
        vehicles_data.append({
            "id": vehicle.id,
            "registration_number": vehicle.registration_number,
            "owner_name": owner.name,
            "model": vehicle.model,
            "registration_expiry": vehicle.registration_expiry.isoformat(),
            "created_date": vehicle.id,  # Using ID as proxy for creation order
        })
    
    return {
        "vehicles": vehicles_data,
    }
