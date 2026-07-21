import os
import nibabel as nib
from flask import Blueprint, jsonify, current_app

nifti_info_bp = Blueprint('nifti_info', __name__, url_prefix='/api')


def _find_nifti_path(nifti_id: str, filestore_path: str) -> str | None:
    """Search common subdirectories for a NIfTI file matching the given UUID."""
    for subdir in ('test_db_nifti', 'display_nifti', ''):
        candidate = os.path.join(filestore_path, subdir, f'{nifti_id}.nii.gz')
        if os.path.exists(candidate):
            return candidate
    return None


@nifti_info_bp.route('/nifti-info/<uuid:nifti_id>', methods=['GET'])
def get_nifti_info(nifti_id):
    """Return header metadata for a NIfTI file without loading voxel data."""
    filestore_path = current_app.config['FILESTORE_PATH']
    nifti_path = _find_nifti_path(str(nifti_id), filestore_path)

    if not nifti_path:
        return jsonify({'error': 'NIfTI file not found'}), 404

    try:
        img = nib.load(nifti_path)
        header = img.header
        dims = [int(d) for d in header.get_data_shape()[:3]]
        zooms = [round(float(z), 4) for z in header.get_zooms()[:3]]
        return jsonify({
            'dims': dims,
            'voxel_size_mm': zooms,
        })
    except Exception as e:
        current_app.logger.error(f"Failed to read NIfTI header for {nifti_id}: {e}")
        return jsonify({'error': 'Failed to read NIfTI header'}), 500
