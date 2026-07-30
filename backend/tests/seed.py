import datetime
import uuid


def seed_patient(**overrides):
    """Insert and return a Patients row. Sensible defaults, override any field."""
    from app import db
    from models import Patients

    fields = dict(
        origin_cancer="lung",
        tumor_count=1,
        dob=datetime.date(1980, 1, 1),
        sex="F",
        height_cm=165.0,
        weight_kg=60.0,
        systolic_bp=120,
        diastolic_bp=80,
        date_of_original_diagnosis=datetime.date(2020, 1, 1),
        date_of_metastatic_diagnosis=datetime.date(2021, 1, 1),
    )
    fields.update(overrides)
    p = Patients(**fields)
    db.session.add(p)
    db.session.commit()
    return p


_GEOM = dict(
    x_com=0, y_com=0, z_com=0,
    x_min=0, x_max=1, y_min=0, y_max=1, z_min=0, z_max=1,
)


def seed_tumor(patient, location, volume_mm3):
    """Create a NiftiData(tumor_mask) + TumorMask pair for a patient."""
    from app import db
    from models import NiftiData, TumorMask

    nid = uuid.uuid4()
    db.session.add(NiftiData(id=nid, patient_id=patient.id, series_type="tumor_mask"))
    db.session.add(TumorMask(id=nid, location=location, volume_mm3=volume_mm3, **_GEOM))
    db.session.commit()


def seed_dose(patient, max_dose, volume_mm3=100.0):
    """Create a NiftiData(dose_mask) + DoseMask pair for a patient."""
    from app import db
    from models import NiftiData, DoseMask

    nid = uuid.uuid4()
    db.session.add(NiftiData(id=nid, patient_id=patient.id, series_type="dose_mask"))
    db.session.add(DoseMask(id=nid, max_dose=max_dose, volume_mm3=volume_mm3, **_GEOM))
    db.session.commit()


def seed_filter(fake_redis, user_id, filter_id, criteria):
    """Write a stored filter into the fake Redis under this user's key."""
    import json
    payload = {filter_id: {"name": "Test Filter", "criteria": criteria}}
    fake_redis.set_path(f"stored_filters:{user_id}", json.dumps(payload))
