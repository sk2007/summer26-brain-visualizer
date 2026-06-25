import os
import numpy as np
import nibabel as nib

SHAPE = (31, 100, 100)
VOXEL_SIZE = (3.5, 1.3, 1.3)
Z_GRID, Y_GRID, X_GRID = np.ogrid[:SHAPE[0], :SHAPE[1], :SHAPE[2]]


def _save_nifti(volume, filepath):
    affine = np.array([
        [VOXEL_SIZE[2], 0, 0, 0],
        [0, VOXEL_SIZE[1], 0, 0],
        [0, 0, VOXEL_SIZE[0], 0],
        [0, 0, 0, 1]
    ], dtype=np.float32)
    nib.save(nib.Nifti1Image(volume, affine), filepath)


def _approx_radius(t):
    rx = (t.x_max - t.x_min) / 2
    ry = (t.y_max - t.y_min) / 2
    rz = (t.z_max - t.z_min) / 2
    return max((rx + ry + rz) / 3, 0.5)


def generate_patient_nifti(nifti_data_id, filestore_path):
    """Generate a NIfTI file on demand for a specific NiftiData record.

    Mirrors the generation logic in generate_sample_nifti.py so the output
    is visually consistent with originally generated files.

    Returns the file path on success, None if the record doesn't exist.
    """
    from app import db
    from models import NiftiData, TumorMask, MRIMask

    nifti_record = db.session.query(NiftiData).filter(
        NiftiData.id == str(nifti_data_id)
    ).first()
    if not nifti_record:
        return None

    out_dir = os.path.join(filestore_path, 'test_db_nifti')
    os.makedirs(out_dir, exist_ok=True)
    filepath = os.path.join(out_dir, f'{nifti_data_id}.nii.gz')

    patient_id = nifti_record.patient_id
    base_seed = hash(str(patient_id)) % 2147483647

    tumor_masks = db.session.query(TumorMask).join(
        NiftiData, NiftiData.id == TumorMask.id
    ).filter(NiftiData.patient_id == patient_id).all()

    tumors = [{'x': t.x_com, 'y': t.y_com, 'z': t.z_com, 'r': _approx_radius(t)}
              for t in tumor_masks]

    series_type = nifti_record.series_type

    if series_type == 'tumor_mask':
        tumor = db.session.query(TumorMask).filter(
            TumorMask.id == str(nifti_data_id)
        ).first()
        volume = np.zeros(SHAPE, dtype=np.uint8)
        if tumor:
            r = _approx_radius(tumor)
            dist = np.sqrt(
                (X_GRID - tumor.x_com) ** 2 +
                (Y_GRID - tumor.y_com) ** 2 +
                (Z_GRID - tumor.z_com) ** 2
            )
            volume[dist <= r] = 1

    elif series_type == 'mri_mask':
        mri_scans = db.session.query(NiftiData).join(
            MRIMask, MRIMask.id == NiftiData.id
        ).filter(
            NiftiData.patient_id == patient_id,
            NiftiData.series_type == 'mri_mask'
        ).order_by(MRIMask.timepoint.asc()).all()

        timepoint_idx = next(
            (i for i, s in enumerate(mri_scans) if str(s.id) == str(nifti_data_id)),
            0
        )

        np.random.seed(base_seed + timepoint_idx)
        volume = np.random.normal(0, 2.5, SHAPE).astype(np.float32)
        np.clip(volume, -10, 10, out=volume)

        for t in tumors:
            dist = np.sqrt(
                (X_GRID - t['x']) ** 2 +
                (Y_GRID - t['y']) ** 2 +
                (Z_GRID - t['z']) ** 2
            )
            enhancement = 3.0 + (timepoint_idx * 0.2)
            volume += np.exp(-dist / (t['r'] * 0.8)) * enhancement

        np.clip(volume, -10, 10, out=volume)

    elif series_type == 'dose_mask':
        np.random.seed(base_seed + 1000)
        volume = np.zeros(SHAPE, dtype=np.float32)
        total_voxels = int(np.prod(SHAPE))
        num_spots = int(total_voxels * 0.03)
        indices = np.random.choice(total_voxels, num_spots, replace=False)
        zc, yc, xc = np.unravel_index(indices, SHAPE)
        doses = np.random.gamma(shape=2, scale=10, size=num_spots)
        np.clip(doses, 0, 70, out=doses)
        volume[zc, yc, xc] = doses

        for t in tumors:
            dist = np.sqrt(
                (X_GRID - t['x']) ** 2 +
                (Y_GRID - t['y']) ** 2 +
                (Z_GRID - t['z']) ** 2
            )
            region = np.where(dist <= (t['r'] * 1.5))
            if len(region[0]) > 0:
                enhanced = np.random.gamma(shape=3, scale=15, size=len(region[0]))
                np.clip(enhanced, 20, 70, out=enhanced)
                volume[region] = np.maximum(volume[region], enhanced)

    else:
        return None

    _save_nifti(volume, filepath)
    return filepath
