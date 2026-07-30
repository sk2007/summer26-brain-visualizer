from flask import Blueprint, jsonify, request
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


def _get_patient_ids_for_filter(filter_id):
    """Return a list of patient UUIDs that match the stored filter criteria."""
    from blueprints.filters import get_stored_filters
    # get_stored_filters returns dict keyed by filter_id
    stored = get_stored_filters()
    if filter_id not in stored:
        # default: all patients
        return [str(p.id) for p in Patients.query.with_entities(Patients.id).all()]
    criteria = stored[filter_id].get('criteria', {})
    # Query patients directly using demographic criteria.
    q = Patients.query
    demo = criteria.get('patient_demographics', {})
    if demo.get('sex'):
        q = q.filter(Patients.sex.in_(demo['sex']))
    if demo.get('origin_cancer'):
        q = q.filter(Patients.origin_cancer.in_(demo['origin_cancer']))
    # age_range, height_range, weight_range are stored as FilterOption {label, min, max} lists
    for field_name, db_col in [
        ('age_range', None),  # handled separately via dob — skipped for now
        ('height_range', Patients.height_cm),
        ('weight_range', Patients.weight_kg),
        ('tumor_count_range', Patients.tumor_count),
    ]:
        opts = demo.get(field_name, [])
        if opts and field_name != 'age_range':
            for opt in opts:
                if isinstance(opt, dict):
                    if opt.get('min') is not None:
                        q = q.filter(db_col >= opt['min'])
                    if opt.get('max') is not None:
                        q = q.filter(db_col <= opt['max'])
    clinical = criteria.get('clinical_data', {})
    for field_name, db_col in [
        ('systolic_bp_range', Patients.systolic_bp),
        ('diastolic_bp_range', Patients.diastolic_bp),
    ]:
        opts = clinical.get(field_name, [])
        for opt in opts:
            if isinstance(opt, dict):
                if opt.get('min') is not None:
                    q = q.filter(db_col >= opt['min'])
                if opt.get('max') is not None:
                    q = q.filter(db_col <= opt['max'])
    return [str(p.id) for p in q.with_entities(Patients.id).all()]


def _fetch_field_values(field_key, patient_ids):
    """Return a list of values for the given field across the provided patient IDs."""
    if not patient_ids:
        return []
    meta = FIELD_REGISTRY.get(field_key)
    if not meta:
        return []
    table = meta['table']

    if table == 'patient':
        rows = Patients.query.filter(Patients.id.in_(patient_ids)).all()
        if field_key == 'patient_age':
            today = datetime.date.today()
            return [
                today.year - p.dob.year - ((today.month, today.day) < (p.dob.month, p.dob.day))
                for p in rows
            ]
        attr_map = {
            'patient_height_cm': 'height_cm',
            'patient_weight_kg': 'weight_kg',
            'patient_systolic_bp': 'systolic_bp',
            'patient_diastolic_bp': 'diastolic_bp',
            'patient_tumor_count': 'tumor_count',
            'patient_sex': 'sex',
            'patient_origin_cancer': 'origin_cancer',
        }
        attr = attr_map.get(field_key)
        return [getattr(p, attr) for p in rows] if attr else []

    if table == 'tumor':
        rows = (
            TumorMask.query
            .join(NiftiData, TumorMask.id == NiftiData.id)
            .filter(NiftiData.patient_id.in_(patient_ids))
            .all()
        )
        if field_key == 'tumor_volume_mm3':
            return [r.volume_mm3 for r in rows]
        if field_key == 'tumor_location':
            return [r.location for r in rows]

    if table == 'dose':
        rows = (
            DoseMask.query
            .join(NiftiData, DoseMask.id == NiftiData.id)
            .filter(NiftiData.patient_id.in_(patient_ids))
            .all()
        )
        if field_key == 'dose_max_dose':
            return [r.max_dose for r in rows]
        if field_key == 'dose_volume_mm3':
            return [r.volume_mm3 for r in rows]

    return []


@chart_fields_bp.route('/chart-data', methods=['POST'])
def get_chart_data():
    """Fetch x and y value arrays for two chosen fields, scoped to a filter."""
    body = request.get_json(silent=True) or {}
    filter_id = body.get('filter_id', 'default_id')
    x_field = body.get('x_field')
    y_field = body.get('y_field')

    if not x_field or not y_field:
        return jsonify({'error': 'x_field and y_field are required'}), 400
    if x_field not in FIELD_REGISTRY or y_field not in FIELD_REGISTRY:
        return jsonify({'error': 'unknown field key'}), 400

    patient_ids = _get_patient_ids_for_filter(filter_id)
    x_values = _fetch_field_values(x_field, patient_ids)
    y_values = _fetch_field_values(y_field, patient_ids)

    # For scatter/line: pair rows. For cross-table fields, pair by positional index
    # (lengths may differ when mixing patient vs. tumor fields).
    return jsonify({'x': x_values, 'y': y_values})
