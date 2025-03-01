import io
import os
import cv2
import numpy as np
import potrace
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)  # Enable Cross-Origin Resource Sharing if needed

# --- Helper Functions ---

def get_bezier_strings_from_trace(trace):
    """
    Convert the traced curves into a list of string expressions representing Bezier curves.
    The curve coordinates are rotated 180° (i.e. (x,y) -> (-x, -y)).
    """
    bezier_strings = []
    for curve in trace.curves:
        segments = curve.segments
        start = curve.start_point  # (x0, y0)
        for segment in segments:
            x0, y0 = start
            if segment.is_corner:
                x1, y1 = segment.c         # The corner point
                x2, y2 = segment.end_point   # The end of the segment
                # Each linear expression is wrapped to flip sign: (-(...))
                expr1 = '(-((1-t)*{:.3f}+t*{:.3f}), -((1-t)*{:.3f}+t*{:.3f}))'.format(x0, x1, y0, y1)
                expr2 = '(-((1-t)*{:.3f}+t*{:.3f}), -((1-t)*{:.3f}+t*{:.3f}))'.format(x1, x2, y1, y2)
                bezier_strings.extend([expr1, expr2])
            else:
                # For smooth curves, assume a cubic Bezier segment.
                x1, y1 = segment.c1
                x2, y2 = segment.c2
                x3, y3 = segment.end_point
                expr = (
                    '(-((1-t)*((1-t)*((1-t)*{:.3f}+t*{:.3f})+t*((1-t)*{:.3f}+t*{:.3f}))+'
                    't*((1-t)*((1-t)*{:.3f}+t*{:.3f})+t*((1-t)*{:.3f}+t*{:.3f}))),'
                    ' -((1-t)*((1-t)*((1-t)*{:.3f}+t*{:.3f})+t*((1-t)*{:.3f}+t*{:.3f}))+'
                    't*((1-t)*((1-t)*{:.3f}+t*{:.3f})+t*((1-t)*{:.3f}+t*{:.3f}))))'
                ).format(
                    x0, x1, x1, x2, x1, x2, x2, x3,
                    y0, y1, y1, y2, y1, y2, y2, y3
                )
                bezier_strings.append(expr)
            start = segment.end_point
    return bezier_strings


def get_contours_from_image(image):
    """
    Convert the input image to grayscale and detect edges using Canny with balanced thresholds.
    """
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    # Lower the minimum threshold to detect more edges
    edges = cv2.Canny(gray, 50, 150)  # Changed from (100, 200)
    return edges

def get_trace_from_contours(contours):
    """
    Create a potrace.Bitmap from the edge-detected image with parameters tuned for detail.
    """
    binary = (contours > 0).astype(np.uint8)
    bmp = potrace.Bitmap(binary)
    trace = bmp.trace(
        turdsize=4,         # Reduced from 7 - keep smaller details
        turnpolicy=potrace.TURNPOLICY_MINORITY,
        alphamax=1.0,       # Reduced from 3.0 - preserve more corners
        opticurve=1,
        opttolerance=0.4    # Increased from 0.2 - more precise curves
    )
    return trace

# --- Flask Endpoint ---

@app.route('/process_image', methods=['POST'])
def process_image():
    """
    Endpoint that receives an image file and returns simplified Bezier curves.
    """
    if 'image' not in request.files:
        return jsonify({'error': 'No image file provided.'}), 400

    file = request.files['image']
    if file.filename == '':
        return jsonify({'error': 'No selected file.'}), 400

    try:
        # Read the uploaded file into memory
        in_memory_file = io.BytesIO()
        file.save(in_memory_file)
        data = np.frombuffer(in_memory_file.getvalue(), dtype=np.uint8)
        # Decode the image from the raw bytes
        image = cv2.imdecode(data, cv2.IMREAD_COLOR)
        if image is None:
            return jsonify({'error': 'Invalid image file.'}), 400

        # Process the image to detect edges
        contours = get_contours_from_image(image)
        # Trace the contours to get vector curves
        trace = get_trace_from_contours(contours)
        # Convert the traced curves into Bezier curve strings
        bezier_strings = get_bezier_strings_from_trace(trace)

        # Adjusted curve limit for more detail
        MAX_CURVES = 5000  # Increased from 3500
        if len(bezier_strings) > MAX_CURVES:
            # Use more sophisticated sampling to preserve detail
            # Take more curves from complex regions
            complexity_scores = [len(curve) for curve in bezier_strings]
            sorted_indices = sorted(range(len(complexity_scores)), 
                                 key=lambda k: complexity_scores[k], 
                                 reverse=True)
            selected_indices = sorted_indices[:MAX_CURVES]
            selected_indices.sort()  # Keep original order
            bezier_strings = [bezier_strings[i] for i in selected_indices]

        # Return simplified response with curve count
        return jsonify({
            'result': bezier_strings,
            'count': len(bezier_strings),
            'params': {
                'edge_low': 50,
                'edge_high': 150,
                'turdsize': 4,
                'alphamax': 1.0,
                'opttolerance': 0.4
            }
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    # Run the Flask app locally on port 5000.
    app.run(host='127.0.0.1', port=5000, debug=True)


