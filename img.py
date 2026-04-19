import cv2
import time


cpt = 0 
maxFrame = 100


count = 0

cap = cv2.VideoCapture('parking1.mp4')

width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

while cpt < maxFrame:
    ret, frame = cap.read()
    if not ret:
        break
    cpt += 1

    if count % 3 != 0:
        continue
    #frame = cv2.resize(frame, (width, height))
    frame = cv2.resize(frame, (750, 750))
    #frame = cv2.resize(frame, None, fx=0.8, fy=0.8)
    cv2.imshow('Frame', frame)    
    cv2.imwrite(f'images/image_{count}.jpg', frame)
    #cpt += 1
    count += 1
    
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break
cap.release()
cv2.destroyAllWindows()