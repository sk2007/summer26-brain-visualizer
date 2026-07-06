from flask import current_app, request, jsonify
from db_loading.nifti_loading import load_nifti
from flask import Blueprint, send_from_directory
import cortex
import os
import shutil
from app import redis_cache

_template_patch_applied = False

viewer = Blueprint('viewer', __name__, url_prefix='/api')

@viewer.route('/viewer/<uuid:nifti_id_str>/<path:nifti_dir>')
@viewer.route('/viewer')
def req_visualize_brain(nifti_id_str=None, nifti_dir=None):
    if nifti_id_str and nifti_dir:
        # Check if this is an asset request (contains file extension or starts with common asset paths)
        if ('.' in nifti_dir and nifti_dir.split('.')[-1].lower() in ['json', 'png', 'jpg', 'jpeg', 'gif', 'css', 'js', 'svg', 'ctm']) or \
           nifti_dir.startswith(('resources/', 'data/', 'css/', 'js/', 'images/')):
            # This is an asset request - serve from shared directory
            return serve_pycortex_shared_assets(nifti_dir)
        
        redis_key = f'viewer_cache:{nifti_id_str}'
        
        if redis_cache.path_exists(redis_key):
            out_path = redis_cache.get_path(redis_key)
            if isinstance(out_path, bytes):
                out_path = out_path.decode('utf-8')
            if os.path.exists(os.path.join(out_path, 'index.html')):
                return send_from_directory(out_path, 'index.html')
            # Stale cache entry (viewer was never fully built) — fall through to regenerate
            redis_cache.delete_path(redis_key)

        filestore_path = current_app.config['FILESTORE_PATH']
        out_path = os.path.abspath(os.path.join(
            filestore_path, 'viewer_cache',
            str(nifti_id_str),
        ))
        redis_cache.set_path(redis_key, out_path)

        nifti_file_path = os.path.join(
            filestore_path,
            nifti_dir,
            f'{nifti_id_str}.nii.gz'
        )
        
        if not os.path.exists(nifti_file_path):
            current_app.logger.info(f"NIfTI not found at {nifti_file_path}, generating on demand...")
            from db_loading.generate_patient_nifti import generate_patient_nifti
            result = generate_patient_nifti(nifti_id_str, filestore_path)
            if not result:
                from flask import abort
                abort(404)
            
    else: # no nifti_id_str or nifti_dir, so we use the mask type from query parameter
        # Get mask type from query parameter, default to tumor if not specified
        mask_type = request.args.get('maskType', 'tumor')
        
        # For now, use default filter since we're not tracking per-user state yet
        # This will be updated when we implement proper user sessions
        current_filter_id = 'default_id'
        
        current_app.logger.info(f"Using filter ID: {current_filter_id}, mask type: {mask_type}")

        redis_key = f'viewer_cache:{current_filter_id}_{mask_type}'
        if redis_cache.path_exists(redis_key):
            out_path = redis_cache.get_path(redis_key)
            if isinstance(out_path, bytes):
                out_path = out_path.decode('utf-8')
            if os.path.exists(os.path.join(out_path, 'index.html')):
                return send_from_directory(out_path, 'index.html')
            # Stale cache entry (e.g. container restarted) — fall through to regenerate
            redis_cache.delete_path(redis_key)

        # Map mask types to cache directories
        cache_subdirs = {
            'tumor': 'tumor_mask_cache',
            'mri': 'mri_mask_cache', 
            'dose': 'dose_mask_cache'
        }

        cache_subdir = cache_subdirs.get(mask_type, 'tumor_mask_cache')

        filestore_path = current_app.config['FILESTORE_PATH']
        out_path = os.path.abspath(os.path.join(
            filestore_path, 'viewer_cache',
            current_filter_id,
            mask_type,
        ))
        redis_cache.set_path(redis_key, out_path)

        # Use the Docker volume path for NIfTI files with mask type subdirectory
        nifti_file_path = os.path.join(
            filestore_path, 
            cache_subdir,
            f"{current_filter_id}.nii.gz"
        )
        
        # Generate the default NIfTI on first request if it doesn't exist yet
        if not os.path.exists(nifti_file_path):
            current_app.logger.info(f"NIfTI not found at {nifti_file_path}, generating for default filter...")
            from db_loading.generate_display_nifti import generate_display_nifti
            result = generate_display_nifti(current_filter_id, {}, mask_type)
            if not result:
                current_app.logger.error("Could not generate display NIfTI — no matching records in database")
                from flask import abort
                abort(404)

    try:
        current_nii = load_nifti(nifti_file_path)
        current_nii_volume_data = current_nii[0]

        # Use a shared directory for common files and session-specific for index.html
        filestore_path = current_app.config['FILESTORE_PATH']
        shared_out_path = os.path.join(filestore_path, 'viewer_cache', 'pycortex_shared')
        session_out_path = out_path
        
        # Ensure both directories exist
        os.makedirs(shared_out_path, exist_ok=True)
        os.makedirs(session_out_path, exist_ok=True)
        
        # Center colormap at 0 so zero voxels appear neutral (white) and tumor signal appears red
        vmax = float(max(abs(current_nii_volume_data.max()), abs(current_nii_volume_data.min()), 1e-6))
        current_nii_volume = cortex.Volume(current_nii_volume_data, subject='S1', xfmname='fullhead', vmin=-vmax, vmax=vmax)

        # Apply template patch lazily so pycortex can find custom_viewer.html
        global _template_patch_applied
        if not _template_patch_applied:
            from patches import template_patch  # noqa: F401 — side-effect import applies the patch
            _template_patch_applied = True

        # Create the static viewer files in shared directory
        cortex.webgl.make_static(outpath=shared_out_path, data={ 'test': current_nii_volume }, recache=True, template='custom_viewer.html', labels_visible=(), overlays_visible=('sulci',))
        
        # Move only the index.html to the session-specific directory
        shared_index = os.path.join(shared_out_path, 'index.html')
        session_index = os.path.join(session_out_path, 'index.html')
        
        if os.path.exists(shared_index):
            shutil.move(shared_index, session_index)
        
        return send_from_directory(session_out_path, 'index.html')
        
    except Exception as e:
        current_app.logger.error(f"Error in /viewer: {e}")
        from flask import abort
        abort(500)

# serve files from shared pycortex directory (catches all resource requests)
@viewer.route('/<path:file_path>')
def serve_pycortex_shared_assets(file_path):
    filestore_path = current_app.config['FILESTORE_PATH']
    shared_directory = os.path.join(filestore_path, 'viewer_cache', 'pycortex_shared')
    
    # Split into directory and filename
    file_directory = os.path.dirname(file_path)
    filename = os.path.basename(file_path)
    
    if file_directory:
        full_directory = os.path.join(shared_directory, file_directory)
    else:
        full_directory = shared_directory
    
    # Security check: ensure we're only serving from the shared directory
    abs_full_dir = os.path.abspath(full_directory)
    abs_shared_dir = os.path.abspath(shared_directory)
    
    if not abs_full_dir.startswith(abs_shared_dir):
        from flask import abort
        abort(404)
    
    # Verify the file exists
    file_full_path = os.path.join(full_directory, filename)
    if not os.path.exists(file_full_path):
        from flask import abort
        abort(404)
    
    return send_from_directory(full_directory, filename)