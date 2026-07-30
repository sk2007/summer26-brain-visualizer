from flask import Blueprint, jsonify
from models import Patients, TumorMask, DoseMask, MRIMask, NiftiData
from app import db
from sqlalchemy import func, extract
import datetime

chart_fields_bp = Blueprint('chart_fields', __name__, url_prefix='/api')

# Registry of queryable fields. key = the string the frontend sends back.
FIELD_REGISTRY = {
    # ── Patient demographics ───────────────────────────────────────────────
    'patient_age': {
        'label': 'Patient Age (years)',
        'type': 'numeric',
        'table': 'patient',
    },
    'patient_height_cm': {
        'label': 'Height (cm)',
        'type': 'numeric',
        'table': 'patient',
    },
    'patient_weight_kg': {
        'label': 'Weight (kg)',
        'type': 'numeric',
        'table': 'patient',
    },
    'patient_systolic_bp': {
        'label': 'Systolic BP (mmHg)',
        'type': 'numeric',
        'table': 'patient',
    },
    'patient_diastolic_bp': {
        'label': 'Diastolic BP (mmHg)',
        'type': 'numeric',
        'table': 'patient',
    },
    'patient_tumor_count': {
        'label': 'Tumor Count',
        'type': 'numeric',
        'table': 'patient',
    },
    'patient_sex': {
        'label': 'Sex',
        'type': 'categorical',
        'table': 'patient',
    },
    'patient_origin_cancer': {
        'label': 'Cancer Type',
        'type': 'categorical',
        'table': 'patient',
    },
    # ── Tumor mask stats ──────────────────────────────────────────────────
    'tumor_volume_mm3': {
        'label': 'Tumor Volume (mm³)',
        'type': 'numeric',
        'table': 'tumor',
    },
    'tumor_location': {
        'label': 'Tumor Location',
        'type': 'categorical',
        'table': 'tumor',
    },
    # ── Dose mask stats ────────────────────────────────────────────────────
    'dose_max_dose': {
        'label': 'Max Dose (Gy)',
        'type': 'numeric',
        'table': 'dose',
    },
    'dose_volume_mm3': {
        'label': 'Dose Volume (mm³)',
        'type': 'numeric',
        'table': 'dose',
    },
}


@chart_fields_bp.route('/chart-fields', methods=['GET'])
def get_chart_fields():
    """Return the list of fields available for chart axes."""
    fields = [
        {'key': key, 'label': meta['label'], 'type': meta['type']}
        for key, meta in FIELD_REGISTRY.items()
    ]
    return jsonify({'fields': fields})
