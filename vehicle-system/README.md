# Vehicle Registration and License Issuance System

This project demonstrates a simple vehicle registration and license issuance system that:

- stores owner and vehicle information in a relational DBMS (SQLite + SQLAlchemy)
- maintains license renewal reminders in MongoDB
- validates duplicate registrations and expired documents
- exposes REST endpoints via FastAPI

## Features

- Owner registration with unique national ID
- Vehicle registration with unique registration and chassis numbers
- License issuance tied to owner and vehicle
- Renewal reminder storage in MongoDB
- Exception handling for expired registrations and duplicate entities

## Setup

1. Install dependencies

```bash
python -m pip install -r requirements.txt
```

2. Make sure MongoDB is running locally on `localhost:27017` or set `MONGODB_URI` and `MONGODB_DB` in the environment.

3. Start the server

```bash
uvicorn app:app --reload
```

## Endpoints

- `GET /` - simple user interface
- `POST /owners/register`
- `POST /licenses/issue`
- `POST /licenses/{license_id}/renew`
- `GET /reminders`
- `GET /licenses/{license_id}`

## Notes

- SQLite is used as a sample DBMS for owner, vehicle, and license storage.
- MongoDB stores renewal reminder records so the system can keep a dedicated reminder feed.
