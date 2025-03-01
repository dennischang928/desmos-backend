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
    Convert the input image to grayscale and detect edges using Canny with higher thresholds.
    """
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    # Increased thresholds to detect only stronger edges
    edges = cv2.Canny(gray, 100, 200)  # Changed from (30, 200)
    return edges

def get_trace_from_contours(contours):
    """
    Create a potrace.Bitmap from the edge-detected image and trace it with aggressive simplification.
    """
    binary = (contours > 0).astype(np.uint8)
    bmp = potrace.Bitmap(binary)
    trace = bmp.trace(
        turdsize=7,        # Increased from 5 - ignore smaller areas
        turnpolicy=potrace.TURNPOLICY_MINORITY,
        alphamax=3,       # Increased from 2.0 - more aggressive curve smoothing
        opticurve=1,
        opttolerance=0.2    # Reduced from 0.5 - less precise but simpler curves
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

        # Limit the number of curves
        MAX_CURVES = 3500  # Adjust this value as needed
        if len(bezier_strings) > MAX_CURVES:
            # Take every nth curve to get approximately MAX_CURVES curves
            step = len(bezier_strings) // MAX_CURVES
            bezier_strings = bezier_strings[::step][:MAX_CURVES]

        # Return simplified response with curve count
        return jsonify({
            'result': bezier_strings,
            'count': len(bezier_strings)
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    # Run the Flask app locally on port 5000.
    app.run(host='127.0.0.1', port=5000, debug=True)


