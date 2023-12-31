import cv2
import pytesseract
import numpy as np
import json
import sys
import os
import csv


def save_to_csv(data, output_csv_path):
    with open(output_csv_path, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        # Write header
        writer.writerow(["Box", "Status"])
        # Write the status of each box
        for index, item in enumerate(data, start=1):
            writer.writerow([f"Box {index}", item['status']])
            
# Function to detect QZKL and crop accordingly
def detect_and_crop(image, fixed_width, fixed_height):
    gray_image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    qzkl_coords = get_qzkl_coords(gray_image)

    if len(qzkl_coords) != 4:
        print("Could not detect four 'QZKL' markers.")
        sys.exit()

    tl, tr, br, bl = order_points(qzkl_coords)
    
    dst = np.array([
        [0, 0],
        [fixed_width-1, 0],
        [fixed_width-1, fixed_height-1],
        [0, fixed_height-1]
    ], dtype="float32")
    
    src = np.array([tl, tr, br, bl], dtype="float32")
    M = cv2.getPerspectiveTransform(src, dst)
    warped = cv2.warpPerspective(image, M, (fixed_width, fixed_height))

    return warped


def get_qzkl_coords(image):
    h, w = image.shape
    d = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)
    n_boxes = len(d['text'])
    coords = []
    for i in range(n_boxes):
        if d['text'][i] == "QZKL":
            (x, y, w_box, h_box) = (d['left'][i], d['top'][i], d['width'][i], d['height'][i])
            center_x = x + w_box // 2
            center_y = y + h_box // 2
            coords.append((center_x, center_y))
    return coords

def order_points(points):
    if points[0][0] > points[2][0]:
        points[0], points[2] = points[2], points[0]
    if points[0][1] > points[1][1]:
        top_left, bottom_left = points[1], points[0]
    else:
        top_left, bottom_left = points[0], points[1]
    if points[2][1] > points[3][1]:
        top_right, bottom_right = points[3], points[2]
    else:
        top_right, bottom_right = points[2], points[3]
    return top_left, top_right, bottom_right, bottom_left

# Functions from detect_checkboxes.py
def detect_checkboxes(image, output_image_path, template_path):
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    thresh = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 11, 2)
    text = pytesseract.image_to_string(thresh)
    print(text)
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    checkboxes = []
    min_area = 10000  
    max_area = 200000  

    for contour in contours:
        area = cv2.contourArea(contour)
        if min_area < area < max_area:
            x, y, w, h = cv2.boundingRect(contour)
            roi = thresh[y:y+h, x:x+w]
            cv2.rectangle(image, (x, y), (x+w, y+h), (0, 255, 0), 2)
            checkboxes.append({
                "x": x, 
                "y": y, 
                "w": w, 
                "h": h,
                "label": "label_here"
            })
            label_position = (x, y-10)
            cv2.putText(image, f"({x}, {y})", label_position, cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1, cv2.LINE_AA)

    cv2.imwrite(output_image_path, image)
    with open(template_path, 'w') as f:
        json.dump(checkboxes, f, indent=4)

def detect_checked_boxes(image, image_path, template_path, threshold=230):
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    # Load checkbox template
    with open(template_path, 'r') as f:
        checkboxes = json.load(f)

    for box in checkboxes:
        x, y, w, h = box["x"], box["y"], box["w"], box["h"]
        
        # Extract the region of interest and calculate its mean intensity
        roi = gray[y:y+h, x:x+w]
        mean_intensity = cv2.mean(roi)[0]

        # Determine if the box is checked
        if mean_intensity < threshold:
            check_status = "pos"
        else:
            check_status = "neg"

        # Label text based on the determined status, coordinate and mean_intensity
        label_text = f"{check_status} ({x}, {y}) Mean:{mean_intensity:.2f}"

        # Draw bounding box
        if check_status == "pos":
            cv2.rectangle(image, (x, y), (x+w, y+h), (0, 255, 0), 2)  # Green for checked
        else:
            cv2.rectangle(image, (x, y), (x+w, y+h), (0, 0, 255), 2)  # Red for unchecked

        # Place the label text above the bounding box
        cv2.putText(image, label_text, (x, y-10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1, cv2.LINE_AA)

    # Generate the output filename based on the image path
    output_path = generate_annotated_filename(image_path)
    cv2.imwrite(output_path, image)
    return output_path

def generate_annotated_filename(original_path, suffix="_annotated"):
    # Split the filename from its extension
    base_name, ext = os.path.splitext(original_path)
    # Append the suffix and return the new filename
    return f"{base_name}{suffix}{ext}"

if __name__ == "__main__":
    if len(sys.argv) != 6:
        print("Usage: python workflow.py <image_path> <mode> <fixed_width> <fixed_height> <threshold>")
        sys.exit(1)

    image_path = sys.argv[1]
    mode = int(sys.argv[2])
    fixed_width = int(sys.argv[3])
    fixed_height = int(sys.argv[4])
    threshold = float(sys.argv[5])

    image = cv2.imread(image_path)

    if mode == 1:
        warped_image = detect_and_crop(image, fixed_width, fixed_height)
        output_image_path = generate_annotated_filename(image_path)
        detect_checkboxes(warped_image, output_image_path, 'template.json')
    elif mode == 2:
        warped_image = detect_and_crop(image, fixed_width, fixed_height)
        checked = detect_checked_boxes(warped_image, image_path, 'template.json', threshold)
        print("Checked boxes:", checked)
