from datetime import date, timedelta
import logging
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from db import Base, engine, SessionLocal
from mongo_client import insert_reminder, find_reminders
from models import Owner, Vehicle, License, OwnerCreate, OwnerResponse, LicenseCreate, LicenseResponse

# Base directory setup
BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

# Create DB tables
Base.metadata.create_all(bind=engine)

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("vehicle_system")

# App instance
app = FastAPI(
    title="Vehicle Registration and License Issuance System",
    description="Stores owners and vehicles in DBMS and keeps reminders in MongoDB",
)

# ✅ CORS (important for frontend)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ✅ Static files (safe handling)
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Root route
@app.get("/", response_class=HTMLResponse)
def read_root():
    html_file = STATIC_DIR / "index.html"
    if not html_file.exists():
        return HTMLResponse("<h1>Frontend not found</h1>")
    return HTMLResponse(html_file.read_text(encoding="utf-8"))

# Utility
def raise_duplicate(message: str):
    raise HTTPException(status_code=400, detail=message)

def validate_vehicle_registration(vehicle: Vehicle):
    if vehicle.registration_expiry < date.today():
        raise HTTPException(status_code=400, detail="Vehicle registration expired")

def create_reminder(owner_id, reg_no, due_date, r_type, message):
    reminder = {
        "owner_id": owner_id,
        "vehicle_registration_number": reg_no,
        "reminder_type": r_type,
        "due_date": due_date,
        "status": "pending",
        "message": message,
    }
    try:
        return insert_reminder(reminder)
    except RuntimeError as e:
        logger.warning(f"MongoDB unavailable: {e}")
        return None

# ------------------- APIs -------------------

@app.post("/owners/register", response_model=OwnerResponse)
def register_owner(payload: OwnerCreate, db: Session = Depends(get_db)):
    if db.query(Owner).filter(Owner.national_id == payload.national_id).first():
        raise_duplicate("Owner already exists")

    if db.query(Vehicle).filter(
        (Vehicle.registration_number == payload.vehicle.registration_number) |
        (Vehicle.chassis_number == payload.vehicle.chassis_number)
    ).first():
        raise_duplicate("Vehicle already exists")

    owner = Owner(**payload.dict(exclude={"vehicle"}))
    db.add(owner)
    db.commit()
    db.refresh(owner)

    vehicle = Vehicle(**payload.vehicle.dict(), owner_id=owner.id)
    db.add(vehicle)
    db.commit()

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
    owner = db.query(Owner).get(payload.owner_id)
    if not owner:
        raise HTTPException(404, "Owner not found")

    vehicle = db.query(Vehicle).get(payload.vehicle_id)
    if not vehicle:
        raise HTTPException(404, "Vehicle not found")

    validate_vehicle_registration(vehicle)

    if db.query(License).filter(License.license_number == payload.license_number).first():
        raise_duplicate("License already exists")

    license_obj = License(**payload.dict(), active=payload.expiry_date >= date.today())
    db.add(license_obj)
    db.commit()
    db.refresh(license_obj)

    create_reminder(owner.id, vehicle.registration_number, payload.expiry_date,
                    "license_renewal", f"License expires on {payload.expiry_date}")

    return license_obj

@app.get("/dashboard/stats")
def dashboard_stats(db: Session = Depends(get_db)):
    return {
        "total_registrations": db.query(Owner).count(),
        "active_vehicles": db.query(Vehicle).filter(Vehicle.registration_expiry >= date.today()).count(),
        "expiring_licenses": db.query(License).filter(
            License.expiry_date <= date.today() + timedelta(days=14)
        ).count(),
        "expired_documents": db.query(License).filter(License.expiry_date < date.today()).count(),
    }
