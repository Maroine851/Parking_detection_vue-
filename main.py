"""
main.py — Logique de détection parking
Utilisé à la fois en standalone ET importé par Django (views.py)
"""
import os
import sys
import cv2

# ── Chemin absolu vers la racine du projet ──────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ── Import de ton module parking.py ─────────────────────────────────────────
from parking import ParkingManagement

# ── Instance GLOBALE du manager (chargée une seule fois) ────────────────────
# Django l'importe et réutilise la même instance → pas de rechargement YOLO
_parking_manager = None

def get_parking_manager():
    """Retourne l'instance singleton de ParkingManagement."""
    global _parking_manager
    if _parking_manager is None:
        _parking_manager = ParkingManagement(
            model=os.path.join(BASE_DIR, "yolov8s.pt"),
            classes=[2, 3, 5, 7],          # car, motorcycle, bus, truck
            json_file=os.path.join(BASE_DIR, "bounding_boxes.json"),
        )
    return _parking_manager


# ── Générateur de frames MJPEG pour Django ───────────────────────────────────
def generate_frames():
    """
    Génère des frames JPEG encodées avec détection YOLO.
    Appelé par Django dans views.py → StreamingHttpResponse.
    """
    video_path = os.path.join(BASE_DIR, "parking1.mp4")
    cap = cv2.VideoCapture(video_path)
    manager = get_parking_manager()

    while True:
        success, frame = cap.read()
        if not success:
            # Reboucler la vidéo
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            continue

        # Resize comme dans l'original
        frame = cv2.resize(frame, (750, 750))

        # ── Appel du modèle YOLO (ton code existant) ──
        processed_frame, spots_status = manager.process_data(
            frame,
            debug=False    # ← False = pas de cv2.imshow (on est en web)
        )

        # Encoder en JPEG pour le stream HTTP
        _, buffer = cv2.imencode('.jpg', processed_frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
        frame_bytes = buffer.tobytes()

        yield (
            b'--frame\r\n'
            b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n'
        )


# ── Récupérer le statut actuel des places ────────────────────────────────────
def get_current_status():
    """
    Retourne le statut actuel de toutes les places.
    Lit bounding_boxes.json + dernière détection en mémoire.
    """
    import json
    manager = get_parking_manager()

    bb_path = os.path.join(BASE_DIR, "bounding_boxes.json")
    with open(bb_path) as f:
        spots_json = json.load(f)

    spots = []
    for region in spots_json:
        name   = region.get("name", "?")
        status = manager.spots_status.get(name, "Free")
        spots.append({
            "id":     name,
            "name":   name,
            "status": status.lower(),   # "free" ou "occupied"
            "price":  manager.price_per_hour,
            "zone":   name[0] if name else "A",
        })
    return spots


# ── Point d'entrée standalone (sans Django) ──────────────────────────────────
if __name__ == "__main__":
    cap = cv2.VideoCapture(os.path.join(BASE_DIR, "parking1.mp4"))
    manager = get_parking_manager()

    while cap.isOpened():
        ret, im0 = cap.read()
        if not ret:
            break

        im0 = cv2.resize(im0, (750, 750))
        im0, spots_status = manager.process_data(im0, debug=True)

        free_spots = [n for n, s in spots_status.items() if s == "Free"]
        print("Places libres:", free_spots)

        if cv2.waitKey(100) & 0xFF == 27:
            break

    cap.release()
    cv2.destroyAllWindows()

    # Afficher l'historique
    print("\n=== PARKING DATA ===\n")
    for spot, cars in manager.parking_data.items():
        print(f"{spot}:")
        for car, info in cars.items():
            if not info:
                continue
            print(f"  - {car} → {info['duration_min']:.2f} min | {info['price_MAD']:.2f} MAD")
        print()