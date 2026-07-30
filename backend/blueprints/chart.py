from flask import Blueprint, jsonify, request, session
from .chart_creators import chart_creation_map

chart = Blueprint('chart', __name__, url_prefix='/api')

def _user_charts_key():
    user_id = session.get('user_id', 'anonymous')
    return f'stored_charts:{user_id}'


def get_stored_charts():
    """Load charts for the current user: Redis first, then DB, then defaults."""
    from app import redis_cache
    from models import SavedChart
    import json

    charts_key = _user_charts_key()
    user_id = session.get('user_id', 'anonymous')

    # 1. Try Redis
    raw = redis_cache.get_path(charts_key)
    if raw:
        if isinstance(raw, bytes):
            raw = raw.decode('utf-8')
        return json.loads(raw)

    # 2. Redis miss: load from DB
    db_charts = SavedChart.query.filter_by(user_id=user_id).all()
    if db_charts:
        charts_dict = {
            c.id: {'type': c.chart_type, 'title': c.title, 'data': c.data}
            for c in db_charts
        }
        store_charts(charts_dict)          # warm the cache
        return charts_dict

    # 3. No saved charts: return defaults (do NOT persist defaults to DB)
    defaults = get_default_charts()
    store_charts(defaults)
    return defaults

def store_charts(charts_dict):
    """Write charts to Redis (always) and sync to DB (skip default IDs)."""
    from app import redis_cache, db
    from models import SavedChart
    import json

    charts_key = _user_charts_key()
    user_id = session.get('user_id', 'anonymous')

    # Always update Redis
    redis_cache.set_path(charts_key, json.dumps(charts_dict))

    # Skip DB writes for the built-in default IDs ("1"–"6")
    default_ids = set(get_default_charts().keys())
    user_chart_ids = set(charts_dict.keys()) - default_ids
    if not user_chart_ids:
        return

    try:
        # Upsert user charts to DB
        existing_ids = {
            c.id for c in SavedChart.query.filter(
                SavedChart.user_id == user_id,
                SavedChart.id.in_(user_chart_ids)
            ).all()
        }
        for chart_id in user_chart_ids:
            info = charts_dict[chart_id]
            if chart_id in existing_ids:
                SavedChart.query.filter_by(id=chart_id, user_id=user_id).update({
                    'chart_type': info['type'],
                    'title': info.get('title'),
                    'data': info['data'],
                })
            else:
                db.session.add(SavedChart(
                    id=chart_id,
                    user_id=user_id,
                    chart_type=info['type'],
                    title=info.get('title'),
                    data=info['data'],
                ))
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f"Error persisting charts to DB: {e}")

def get_default_charts():
    """Create a fresh copy of default charts for each request."""
    return {
        "1": {
            'type': "line_chart",
            'title': "Patient Data Over Time",
            'data': {
                'xaxis_title': "Time",
                'yaxis_title': "Value",
                'series': [
                    {
                        'name': "Series 1",
                        'mode': "lines",
                        'trace': { 'x': [1, 2, 3], 'y': [10, 15, 20] },
                        'traceType': "line_chart_trace"
                    }
                ]
            }
        },
        "2": {
            'type': "bar_chart",
            'title': "Patient Data Over Time",
            'data': {
                'xaxis_title': "Time",
                'yaxis_title': "Value",
                'series': [
                    {
                        'name': "Series 1",
                        'mode': "stack",
                        'trace': { 'x': ['San Jose', 'San Francisco', 'Los Angeles'], 'y': [10, 15, 20] },
                        'traceType': "bar_chart_trace"
                    }
                ]
            }
        },
        "3": {
            'type': "scatter_plot",
            'title': "Patient Measurements",
            'data': {
                'xaxis_title': "Height (cm)",
                'yaxis_title': "Weight (kg)",
                'series': [
                    {
                        'name': "Patients",
                        'mode': "markers",
                        'trace': { 'x': [165, 170, 175, 180, 185], 'y': [65, 70, 75, 80, 85] },
                        'traceType': "scatter_plot_trace"
                    }
                ]
            }
        },
        "4": {
            'type': "histogram",
            'title': "Age Distribution",
            'data': {
                'xaxis_title': "Age",
                'yaxis_title': "Count",
                'series': [
                    {
                        'name': "Patient Ages",
                        'trace': { 'x': [22, 25, 28, 30, 31, 32, 35, 38, 42, 45, 48, 50, 52, 55, 58, 60, 65, 70] },
                        'traceType': "histogram_trace"
                    }
                ]
            }
        },
        "5": {
            'type': "box_plot",
            'title': "Blood Pressure Readings",
            'data': {
                'xaxis_title': "Patient Group",
                'yaxis_title': "Blood Pressure",
                'series': [
                    {
                        'name': "Control Group",
                        'trace': { 'y': [120, 118, 122, 125, 130, 128, 135, 132, 137, 140] },
                        'traceType': "box_plot_trace"
                    },
                    {
                        'name': "Test Group",
                        'trace': { 'y': [115, 112, 118, 120, 125, 124, 130, 128, 132, 135] },
                        'traceType': "box_plot_trace"
                    }
                ]
            }
        },
        "6": {
            'type': "bubble_chart",
            'title': "Patient Demographics",
            'data': {
                'xaxis_title': "Age",
                'yaxis_title': "BMI",
                'series': [
                    {
                        'name': "Female Patients",
                        'trace': { 
                            'x': [25, 30, 35, 40, 45, 50], 
                            'y': [21, 22, 23, 25, 26, 27],
                            'size': [20, 40, 30, 50, 35, 25],
                            'text': ["Patient A", "Patient B", "Patient C", "Patient D", "Patient E", "Patient F"]
                        },
                        'traceType': "bubble_chart_trace"
                    }
                ]
            }
        }
    }

def get_brain_clicks():
    """Create a fresh copy of brain clicks for each request."""
    return []

# access all active charts
@chart.route('/charts', methods=['GET'])
def get_charts():
    processed_charts = {}
    active_charts_copy = get_stored_charts() # Get a fresh copy for each request
    for chart_id, chart_info in active_charts_copy.items():
        chart_type = chart_info.get('type')
        data_payload = chart_info.get('data')
        title = chart_info.get('title')

        if chart_type and data_payload and chart_type in chart_creation_map:
            try:
                # Add title to payload as create_line_chart expects it inside data
                payload_with_title = {**data_payload, 'title': title} 
                plotly_config = chart_creation_map[chart_type](payload_with_title)
                
                # Check if the creation function returned an error tuple (jsonify(), status_code)
                if isinstance(plotly_config, tuple) and len(plotly_config) == 2 and isinstance(plotly_config[1], int):
                     print(f"Error generating config for chart {chart_id}: {plotly_config[0].get_json()}")
                     continue # Skip adding this chart to the response
                
                processed_charts[chart_id] = plotly_config
            except Exception as e:
                print(f"Exception generating config for chart {chart_id}: {str(e)}")
                # Optionally add error info to response, or just skip
        else:
            print(f"Skipping chart {chart_id} due to missing/invalid type or data.")
            
    return jsonify(processed_charts)

# create chart api endpoint
@chart.route('/charts', methods=['POST'])
def create_chart():
    type = request.json.get('type')
    id = request.json.get('id')
    data = request.json.get('data')
    title = request.json.get('title')
    
    # Reject IDs that collide with built-in defaults to prevent Redis corruption
    if id in get_default_charts():
        return jsonify({'error': 'chart id conflicts with a default chart'}), 400

    # Store the chart definition
    active_charts_copy = get_stored_charts() # Get charts from Redis
    active_charts_copy[id] = {
        'type': type,
        'title': title,
        'data': data
    }
    
    # Store the updated charts back to Redis
    store_charts(active_charts_copy)
    
    # Generate chart configuration using the appropriate creator function
    return_chart = chart_creation_map[type](data)
    
    return jsonify(return_chart)

# modify chart
@chart.route('/charts/<id>', methods=['PUT'])
def modify_chart(id):
    type = request.json.get('type')
    data = request.json.get('data')
    title = request.json.get('title') # Also get title for modification

    active_charts_copy = get_stored_charts() # Get charts from Redis
    if id not in active_charts_copy:
        return jsonify({ 'error': 'invalid chart id' }), 404 # Use 404 for not found
    
    if not type or type not in chart_creation_map:
        return jsonify({ 'error': 'invalid chart type' }), 400

    if not data:
         return jsonify({ 'error': 'missing chart data' }), 400

    try:
        # Prepare payload, similar to GET
        payload_with_title = {**data, 'title': title}
        modified_chart_config = chart_creation_map[type](payload_with_title)

        # Check for error response from creation function
        if isinstance(modified_chart_config, tuple) and len(modified_chart_config) == 2 and isinstance(modified_chart_config[1], int):
            return modified_chart_config # Return the error response directly

        # We need to update active_charts with the NEW definition, not the config
        active_charts_copy[id] = {'type': type, 'title': title, 'data': data}
        
        # Store the updated charts back to Redis
        store_charts(active_charts_copy)

        return jsonify(modified_chart_config) # Return the newly generated config
    except Exception as e:
        print(f"Error modifying chart {id}: {str(e)}")
        return jsonify({'error': 'Failed to modify chart'}), 500

# delete chart
@chart.route('/charts/<id>', methods=['DELETE']) # Ensure plural 'charts' for consistency
def delete_chart(id):
    active_charts_copy = get_stored_charts()
    if id not in active_charts_copy:
        return jsonify({ 'error': 'no such chart exists' }), 404

    # Delete from DB first — if this fails, we haven't touched Redis yet
    try:
        from app import db
        from models import SavedChart
        user_id = session.get('user_id', 'anonymous')
        SavedChart.query.filter_by(id=id, user_id=user_id).delete()
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f"Error deleting chart from DB: {e}")
        return jsonify({'error': 'Failed to delete chart'}), 500

    del active_charts_copy[id]
    store_charts(active_charts_copy)

    return jsonify({ 'message': 'chart successfully deleted' }), 200

# Brain location click endpoint
@chart.route('/brain-clicks', methods=['POST'])
def store_brain_click():
    """Store a brain location click from pycortex viewer.
    
    Expected JSON format:
    {
        "hemi": "left|right",
        "vertex": 12345,  # Vertex index
        "coords": [x, y, z],  # 3D coordinates
        "timestamp": 1234567890  # Optional
    }
    """
    try:
        click_data = request.json
        if not click_data or not isinstance(click_data, dict):
            return jsonify({"error": "Invalid data format"}), 400
            
        # Validate required fields
        required_fields = ["hemi", "vertex", "coords"]
        for field in required_fields:
            if field not in click_data:
                return jsonify({"error": f"Missing required field: {field}"}), 400
                
        # Add timestamp if not provided
        if "timestamp" not in click_data:
            from datetime import datetime
            click_data["timestamp"] = datetime.now().timestamp()
            
        # Store the click data
        brain_clicks.append(click_data)
        
        return jsonify({
            "status": "success", 
            "message": "Brain click stored",
            "total_clicks": len(brain_clicks)
        }), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Get all brain clicks
@chart.route('/brain-clicks', methods=['GET'])
def get_brain_clicks():
    """Retrieve all stored brain location clicks."""
    return jsonify(brain_clicks)