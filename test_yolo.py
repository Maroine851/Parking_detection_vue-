from parking import ParkingManagement
import cv2

cap = cv2.VideoCapture("Videos/vid1.mp4")

parking_manager = ParkingManagement(
    model="yolov8s.pt",  
    classes=[2, 3, 5, 7],  # car, motorcycle, bus, truck
    json_file="bounding_boxes.json",
)

width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

while cap.isOpened():
    ret, im0 = cap.read()
    if not ret:
        break

    # Resize frame
    im0_resized = cv2.resize(im0, (width, height))
    #im0_resized = cv2.resize(im0, None, fx=0.8, fy=0.8)

    # Detect parking spots and get updated frame + spots status
    im0_resized, spots_status = parking_manager.process_data(im0_resized, 0)

    # Show the frame
    cv2.imshow("Parking Detection", im0_resized)

    # Optional: print occupied/free spots
    print(spots_status)

    if cv2.waitKey(1) & 0xFF == 27:  # ESC to exit
        break

cap.release()
cv2.destroyAllWindows()
