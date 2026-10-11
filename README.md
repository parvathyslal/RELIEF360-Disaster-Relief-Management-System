# RELIEF360 – Disaster Relief Management System

**A PostgreSQL-based disaster relief management system for coordinating emergency response, relief camps, victims, resources, and volunteer activities.**

## Overview

RELIEF360 is a database-driven web application designed to organize and manage disaster relief operations through a centralized platform. It supports disaster registration, relief camp management, victim tracking, missing-person reports, resource distribution, medical assistance, donations, and volunteer coordination.

The application uses a Python backend connected to PostgreSQL, allowing information entered through the web interface to be stored and retrieved from the relational database.

## Key Features

- **Disaster Management:** Register disasters and maintain their status and location details.
- **Relief Camp Management:** Manage camp information, capacity, and occupancy.
- **Victim Management:** Register affected individuals and track camp assignments.
- **Missing-Person Tracking:** Maintain missing-person reports and reunification records.
- **Inventory and Distribution:** Monitor camp-level stock and record resource distributions.
- **Volunteer Management:** Register volunteers and manage assignments.
- **Donation Management:** Record monetary donations and generate receipts.
- **Medical Assistance:** Manage medical cases and treatment updates.
- **Vehicle Management:** Track vehicle allocation and returns.
- **Dashboard and Reports:** View operational summaries, inventory reports, and camp occupancy.

## Technology Stack

| Component | Technology |
|---|---|
| Frontend | HTML, CSS, JavaScript |
| Backend | Python |
| Database | PostgreSQL |
| Database Administration | pgAdmin 4 |
| Database Connectivity | psycopg |
| Version Control | GitHub |

## Database Design

The PostgreSQL database, named `relief360`, consists of **24 interconnected relational tables**.

The implementation incorporates:

- Primary and foreign keys
- CHECK and UNIQUE constraints
- Database normalization
- SQL joins and views
- PL/pgSQL triggers
- Transaction-based inventory operations
- Role-based application permissions

Two reporting views, `camp_occupancy` and `stock_report`, support camp occupancy monitoring and inventory reporting.

## Installation and Setup

### Requirements

- Python 3.10 or later
- PostgreSQL
- pgAdmin 4

### Windows Setup

1. Download or clone the repository.
2. Create an empty PostgreSQL database named `relief360`.
3. Open the project folder.
4. Run `SETUP_WINDOWS.bat`.
5. Enter your PostgreSQL connection details when prompted.
6. After successful setup, run `START_WINDOWS.bat`.
7. Open the application at:

   `http://localhost:8000/login.html`

Alternatively, start the application manually:

```bash
py -m pip install -r requirements.txt
py setup_database.py
py server.py
```

The PostgreSQL service must be running before starting the application.

## Database Connectivity

RELIEF360 connects the web interface to PostgreSQL through a Python backend.

When a user adds, updates, or manages records through the application, the backend processes the request and performs the corresponding database operations.

Changes can be verified using pgAdmin:

```sql
select * from disaster order by disaster_id desc;

select * from camp order by camp_id desc;

select * from missing_report order by report_id desc;
```

Database changes can also be reflected in the web interface after refreshing the relevant module.

## Testing and Validation

The system includes database integrity checks and application-level validation to support reliable data management.

Testing covers:

- Record insertion, retrieval, and updates
- Foreign-key and CHECK constraint enforcement
- SQL joins and reporting views
- Relationship validation
- Inventory transaction consistency
- Web application and PostgreSQL integration

## Future Enhancements

- Cloud deployment and remote accessibility
- Mobile application for field volunteers
- GIS-based disaster and camp visualization
- SMS and email emergency notifications
- Advanced analytics and resource forecasting
- Enhanced authentication, auditing, and data security

## Project Information

**Project:** RELIEF360 – Disaster Relief Management System  
**Category:** Database Management System (DBMS)  
**Database:** PostgreSQL  
**Owner:**Parvathy S Lal
**Institution:** Amrita Vishwa Vidyapeetham, Amritapuri

## License

Developed as an academic project for educational purposes.
