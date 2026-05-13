from datetime import date, timedelta
import logging
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from db import Base, engine, SessionLocal
from mongo_client import insert_reminder
from models import (
    Owner,
    Vehicle,
    License,
    OwnerCreate,
    OwnerResponse,
    LicenseCreate,
    LicenseResponse,
)

# -------------------- Paths --------------------

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

# -------------------- Logging --------------------

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("vehicle_system")

# -------------------- FastAPI App --------------------

app = FastAPI(
    title="Vehicle Registration and License Issuance System",
    description="Stores owners and vehicles in DBMS and reminders in MongoDB",
)

# -------------------- Startup --------------------

@app.on_event("startup")
def startup():
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created successfully")

# -------------------- CORS --------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------- Static Files --------------------

STATIC_DIR.mkdir(exist_ok=True)

app.mount(
    "/static",
    StaticFiles(directory=str(STATIC_DIR)),
    name="static"
)

# -------------------- Database Dependency --------------------

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# -------------------- Root Route --------------------

@app.get("/", response_class=HTMLResponse)
def read_root():
    html_file = STATIC_DIR / "index.html"

    if not html_file.exists():
        return HTMLResponse("<h1>Frontend not found</h1>")

    return HTMLResponse(html_file.read_text(encoding="utf-8"))

# -------------------- Utility Functions --------------------

def raise_duplicate(message: str):
    raise HTTPException(status_code=400, detail=message)

def validate_vehicle_registration(vehicle: Vehicle):
    if vehicle.registration_expiry < date.today():
        raise HTTPException(
            status_code=400,
            detail="Vehicle registration expired"
        )

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

# -------------------- APIs --------------------

@app.post("/owners/register", response_model=OwnerResponse)
def register_owner(
    payload: OwnerCreate,
    db: Session = Depends(get_db)
):

    existing_owner = db.query(Owner).filter(
        Owner.national_id == payload.national_id
    ).first()

    if existing_owner:
        raise_duplicate("Owner already exists")

    existing_vehicle = db.query(Vehicle).filter(
        (Vehicle.registration_number == payload.vehicle.registration_number) |
        (Vehicle.chassis_number == payload.vehicle.chassis_number)
    ).first()

    if existing_vehicle:
        raise_duplicate("Vehicle already exists")

    owner = Owner(**payload.model_dump(exclude={"vehicle"}))

    db.add(owner)
    db.commit()
    db.refresh(owner)

    vehicle = Vehicle(
        **payload.vehicle.model_dump(),
        owner_id=owner.id
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

# -------------------- License API --------------------

@app.post("/licenses/issue", response_model=LicenseResponse)
def issue_license(
    payload: LicenseCreate,
    db: Session = Depends(get_db)
):

    owner = db.query(Owner).filter(
        Owner.id == payload.owner_id
    ).first()

    if not owner:
        raise HTTPException(
            status_code=404,
            detail="Owner not found"
        )

    vehicle = db.query(Vehicle).filter(
        Vehicle.id == payload.vehicle_id
    ).first()

    if not vehicle:
        raise HTTPException(
            status_code=404,
            detail="Vehicle not found"
        )

    validate_vehicle_registration(vehicle)

    existing_license = db.query(License).filter(
        License.license_number == payload.license_number
    ).first()

    if existing_license:
        raise_duplicate("License already exists")

    license_obj = License(
        **payload.model_dump(),
        active=payload.expiry_date >= date.today()
    )

    db.add(license_obj)
    db.commit()
    db.refresh(license_obj)

    create_reminder(
        owner.id,
        vehicle.registration_number,
        payload.expiry_date,
        "license_renewal",
        f"License expires on {payload.expiry_date}"
    )

    return license_obj

# -------------------- Dashboard Stats --------------------

@app.get("/dashboard/stats")
def dashboard_stats(db: Session = Depends(get_db)):

    return {
        "total_registrations":
            db.query(Owner).count(),

        "active_vehicles":
            db.query(Vehicle).filter(
                Vehicle.registration_expiry >= date.today()
            ).count(),

        "expiring_licenses":
            db.query(License).filter(
                License.expiry_date <= date.today() + timedelta(days=14)
            ).count(),

        "expired_documents":
            db.query(License).filter(
                License.expiry_date < date.today()
            ).count(),
    }
