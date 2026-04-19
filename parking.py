import json
import time
import sqlite3

import cv2
import numpy as np

from ultralytics.solutions.solutions import LOGGER, BaseSolution, check_requirements
from ultralytics.utils.plotting import Annotator


class ParkingPtsSelection:
    def __init__(self):
        """Initializes the ParkingPtsSelection class, setting up UI and properties for parking zone point selection."""
        check_requirements("tkinter")
        import tkinter as tk
        from tkinter import filedialog, messagebox

        self.tk, self.filedialog, self.messagebox = tk, filedialog, messagebox
        self.setup_ui()
        self.initialize_properties()
        self.master.mainloop()
        

    def setup_ui(self):
        """Sets up the Tkinter UI components for the parking zone points selection interface."""
        self.master = self.tk.Tk()
        self.master.title("Ultralytics Parking Zones Points Selector")
        self.master.resizable(False, False)

        # Canvas for image display
        self.canvas = self.tk.Canvas(self.master, bg="white")
        self.canvas.pack(side=self.tk.BOTTOM)

        # Button frame with buttons
        button_frame = self.tk.Frame(self.master)
        button_frame.pack(side=self.tk.TOP)

        for text, cmd in [
            ("Upload Image", self.upload_image),
            ("Remove Last BBox", self.remove_last_bounding_box),
            ("Save", self.save_to_json),
        ]:
            self.tk.Button(button_frame, text=text, command=cmd).pack(side=self.tk.LEFT)

    def initialize_properties(self):
        """Initialize properties for image, canvas, bounding boxes, and dimensions."""
        self.image = self.canvas_image = None
        self.rg_data, self.current_box = [], []
        self.imgw = self.imgh = 0
        self.canvas_max_width, self.canvas_max_height = 1020, 500

    def upload_image(self):
        """Uploads and displays an image on the canvas, resizing it to fit within specified dimensions."""
        from PIL import Image, ImageTk  # scope because ImageTk requires tkinter package

        self.image = Image.open(self.filedialog.askopenfilename(filetypes=[("Image Files", "*.png *.jpg *.jpeg")]))
        if not self.image:
            return

        self.imgw, self.imgh = self.image.size
        aspect_ratio = self.imgw / self.imgh
        canvas_width = (
            min(self.canvas_max_width, self.imgw) if aspect_ratio > 1 else int(self.canvas_max_height * aspect_ratio)
        )
        canvas_height = (
            min(self.canvas_max_height, self.imgh) if aspect_ratio <= 1 else int(canvas_width / aspect_ratio)
        )

        self.canvas.config(width=canvas_width, height=canvas_height)
        self.canvas_image = ImageTk.PhotoImage(self.image.resize((canvas_width, canvas_height), Image.LANCZOS))
        self.canvas.create_image(0, 0, anchor=self.tk.NW, image=self.canvas_image)
        self.canvas.bind("<Button-1>", self.on_canvas_click)

        self.rg_data.clear(), self.current_box.clear()

    def on_canvas_click(self, event):
        """Handles mouse clicks to add points for bounding boxes on the canvas."""
        self.current_box.append((event.x, event.y))
        self.canvas.create_oval(event.x - 3, event.y - 3, event.x + 3, event.y + 3, fill="red")
        if len(self.current_box) == 4:
            spot_id = f"P{len(self.rg_data) + 1}"  # Auto name: P1, P2, P3...
    
        self.rg_data.append({
        "name": spot_id,
        "points": self.current_box.copy()
        })

        self.draw_box(self.current_box)

         # Draw the name on canvas
        cx = int(sum([p[0] for p in self.current_box]) / 4)
        cy = int(sum([p[1] for p in self.current_box]) / 4)
        self.canvas.create_text(cx, cy, text=spot_id, fill="yellow", font=("Arial", 12, "bold"))

        self.current_box.clear()

    def draw_box(self, box):
        """Draws a bounding box on the canvas using the provided coordinates."""
        for i in range(4):
            self.canvas.create_line(box[i], box[(i + 1) % 4], fill="blue", width=2)

    def remove_last_bounding_box(self):
        """Removes the last bounding box from the list and redraws the canvas."""
        if not self.rg_data:
            self.messagebox.showwarning("Warning", "No bounding boxes to remove.")
            return
        self.rg_data.pop()
        self.redraw_canvas()

    def redraw_canvas(self):
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, anchor=self.tk.NW, image=self.canvas_image)

        for region in self.rg_data:
            self.draw_box(region["points"])

        # draw name
            pts = region["points"]
            cx = int(sum([p[0] for p in pts]) / 4)
            cy = int(sum([p[1] for p in pts]) / 4)
            self.canvas.create_text(cx, cy, text=region["name"], fill="yellow", font=("Arial", 12, "bold"))

    def save_to_json(self):
        """Saves the selected parking zone points to a JSON file with scaled coordinates."""
        scale_w, scale_h = self.imgw / self.canvas.winfo_width(), self.imgh / self.canvas.winfo_height()
        data = []
        for region in self.rg_data:
            scaled_points = [(int(x * scale_w), int(y * scale_h)) for x, y in region["points"]]
    
            data.append({
                "name": region["name"],
                "points": scaled_points
            })
        with open("bounding_boxes.json", "w") as f:
            json.dump(data, f, indent=4)
        self.messagebox.showinfo("Success", "Bounding boxes saved to bounding_boxes.json")


class ParkingManagement(BaseSolution):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.json_file = self.CFG.get("json_file")
        if not self.json_file:
            LOGGER.warning("❌ json_file argument missing. Parking region details required.")
            raise ValueError("Json file path cannot be empty")

        # Load parking spots with names
        with open(self.json_file) as f:
            self.json = json.load(f)

        self.pr_info = {"Occupancy": 0, "Available": 0}
        self.spots_status = {}  # {spot_name: "Occupied"/"Free"}


        # Colors: Free, Occupied, Car centroid
        self.free_color = (0, 255, 0)
        self.occ_color = (0, 0, 255)
        self.centroid_color = (255, 0, 189)

       
        # === AJOUT: SYSTEME PRIX
        self.entry_time = {}       # Temps d'entrée pour chaque place
        self.current_cars = {}     # True/False (mémoire)
        self.car_counter = {}      # Nombre de voitures par place
        self.parking_data = {}     # Stockage final (durée + prix)..... khasni nqaad l output

        self.time_scale = 60       # 1 sec vidéo = 1 min réelle
        self.price_per_hour =  5 # 5 MAD / heure

        self.conn = sqlite3.connect("parking.db")
        self.cursor = self.conn.cursor()

        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS parking_log(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            spot TEXT,
            car_id TEXT,
            duration REAL,
            price REAL
        )

        """)
        self.conn.commit()

     
    def calculate_price(self, duration_seconds):
        hours = duration_seconds / 360
        return round(hours * self.price_per_hour, 2)
    
    #save the database:

    def save_to_db(self, spot, car_id, duration, price):
        self.cursor.execute(
            "INSERT INTO parking_log (spot, car_id, duration, price) VALUES (?,?, ?, ?)",
             (spot, car_id, duration, price)
        )
        self.conn.commit()

    def process_data(self, im0, current_time=None, debug=True, overlap_threshold=0.25, min_box_area=500):
        """
        Detect parking occupancy.
        Returns the image with drawn rectangles and a dict of spot statuses.
        """

        results = self.model(im0)
        boxes = []
        classes = []

        # Extract YOLO detections
        for r in results:
            # Get the original image (as NumPy array)
            if hasattr(r, "orig_img"):
                im0 = r.orig_img  # this ensures im0 is a proper NumPy array

            for box in r.boxes:
                x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                w, h = x2 - x1, y2 - y1
                if w * h < min_box_area:
                    continue  # ignore very small boxes (shadows/noise)
                boxes.append([int(x1), int(y1), int(x2), int(y2)])
                classes.append(int(box.cls[0]))

        occupied_count, free_count = 0, len(self.json)
        self.spots_status = {}
       
#----------------------------------------oumaima
     
 #Detection de parking

        for region in self.json:
            name = region.get("name", "Unnamed")
           # current_status = self.spots_status.get(name, "Free")
            pts = np.array(region["points"], dtype=np.int32)

            # Create a mask for the parking spot
            mask_region = np.zeros(im0.shape[:2], dtype=np.uint8)
            cv2.fillPoly(mask_region, [pts], 255)

            region_occupied = False

            for box, cls in zip(boxes, classes):
                x1, y1, x2, y2 = box
                mask_box = np.zeros(im0.shape[:2], dtype=np.uint8)
                cv2.rectangle(mask_box, (x1, y1), (x2, y2), 255, -1)

                intersection = cv2.bitwise_and(mask_region, mask_box)
                intersection_ratio = cv2.countNonZero(intersection) / max(1, cv2.countNonZero(mask_region))

                if intersection_ratio > overlap_threshold:
                    region_occupied = True
                    # Draw centroid
                    xc, yc = (x1 + x2) // 2, (y1 + y2) // 2
                    cv2.circle(im0, (xc, yc), 5, self.centroid_color, -1)
                    cv2.putText(im0, self.model.names[int(cls)], (xc, yc + 20),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)
                    break

            if region_occupied:
                occupied_count += 1
                free_count -= 1
                self.spots_status[name] = "Occupied"
                print(name, "OCCUPIED")
            else:
                self.spots_status[name] = "Free"
                print(name, "FREE")

            # Draw rectangle around the spot
            rect = cv2.minAreaRect(pts)
            box_pts = cv2.boxPoints(rect).astype(int)
            cv2.polylines(im0, [box_pts], True, self.occ_color if region_occupied else self.free_color, 2)

            # Put the spot name on the image
            cx, cy = int(np.mean(pts[:, 0])), int(np.mean(pts[:, 1]))
            cv2.putText(im0, name, (cx, cy), cv2.FONT_HERSHEY_SIMPLEX, 0.6,
                        self.occ_color if region_occupied else self.free_color, 2)

 # === LOGIQUE PRIX
        
        current_time = time.time() * self.time_scale  # temps simulé

        for name, status in self.spots_status.items(): #analyse de chaque pakring separement

            # Initialisation
            if name not in self.current_cars:
                self.current_cars[name] = False
                self.entry_time[name] = None
                self.car_counter[name] = 0
                self.parking_data[name] = {}

            # voiture entre
            if status == "Occupied" and not self.current_cars[name]:
                self.current_cars[name] = True
                self.entry_time[name] = current_time

                self.car_counter[name] += 1
                car_id = f"car{self.car_counter[name]}"

                self.parking_data[name][car_id] = {}

            # voiture sort
            elif status == "Free" and self.current_cars[name]:
                self.current_cars[name] = False

                if self.entry_time[name] is not None:
                    duration = current_time - self.entry_time[name]
                    price = self.calculate_price(duration)

                    car_id = f"car{self.car_counter[name]}"

                    self.parking_data[name][car_id] = {
                        "duration_min": round(duration / 60, 2),
                        "price_MAD": price
                    }
                    #savegarde
                    self.save_to_db(name, car_id, round(duration /60, 2), price)

                    print(f"{name} | {car_id} -> {duration/60:.2f} h| {price} MAD")

                    self.entry_time[name] = None

#AFFICHAGE
        self.pr_info["Occupancy"], self.pr_info["Available"] = occupied_count, free_count

        cv2.putText(
    im0,
    f"Occupied: {occupied_count} | Free: {free_count}",
    (10, 30),
    cv2.FONT_HERSHEY_SIMPLEX,
    0.7,
    (255, 255, 255),
    2
)

        # Debug window
        if debug:
            if isinstance(im0, np.ndarray):
                cv2.imshow("Parking Detection", im0)
                cv2.waitKey(1)
            else:
                print("Warning: invalid image for display:", type(im0))

        return im0, self.spots_status

   
