"""
detection/views.py
Connecte Django à ton code ML existant (main.py / parking.py)
"""
import os
import sys
import json

# ── Ajouter la racine du projet au PATH pour importer main.py ──
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from django.shortcuts import render
from django.http import JsonResponse, StreamingHttpResponse

# ── Import de tes fonctions depuis main.py ──
from main import generate_frames, get_current_status, get_parking_manager

# ── Import du model Django pour l'historique ──
from .models import ParkingLog


# ────────────────────────────────────────────────────────
# PAGE PRINCIPALE — Dashboard
# ────────────────────────────────────────────────────────
def dashboard(request):
    """
    Affiche le dashboard principal avec :
    - Le flux vidéo (via <img src="/video/">)
    - Les stats en temps réel
    - L'historique depuis parking.db
    """
    try:
        spots = get_current_status()
    except Exception:
        # Si le modèle n'est pas encore chargé ou bounding_boxes.json vide
        spots = []

    free_spots    = [s for s in spots if s["status"] == "free"]
    occupied      = [s for s in spots if s["status"] == "occupied"]
    total_spots   = len(spots)
    occupancy_pct = round(len(occupied) / max(total_spots, 1) * 100)

    # Historique depuis parking.db
    try:
        history = ParkingLog.objects.order_by('-id')[:20]
        total_video = ParkingLog.objects.count()
    except Exception:
        history     = []
        total_video = 0

    context = {
        "spots":          spots,
        "free_count":     len(free_spots),
        "occupied_count": len(occupied),
        "total_spots":    total_spots,
        "occupancy_pct":  occupancy_pct,
        "total_video":    total_video,
        "history":        history,
    }
    return render(request, "detection/dashboard.html", context)


# ────────────────────────────────────────────────────────
# FLUX VIDÉO MJPEG — src de la balise <img> dans le HTML
# ────────────────────────────────────────────────────────
def video_feed(request):
    """
    Stream MJPEG : chaque frame est traitée par YOLO en temps réel.
    Utilisé dans le template : <img src="{% url 'video_feed' %}">
    """
    return StreamingHttpResponse(
        generate_frames(),
        content_type='multipart/x-mixed-replace; boundary=frame'
    )


# ────────────────────────────────────────────────────────
# API — Stats en temps réel (appellée par JS toutes les 3s)
# ────────────────────────────────────────────────────────
def live_stats(request):
    """
    Endpoint JSON pour rafraîchir les compteurs sans recharger la page.
    """
    try:
        spots = get_current_status()
    except Exception:
        spots = []

    free     = sum(1 for s in spots if s["status"] == "free")
    occupied = len(spots) - free

    return JsonResponse({
        "free":          free,
        "occupied":      occupied,
        "total":         len(spots),
        "occupancy_pct": round(occupied / max(len(spots), 1) * 100),
    })


# ────────────────────────────────────────────────────────
# API — Recherche de places selon prix et durée
# ────────────────────────────────────────────────────────
def search_spots(request):
    """
    Filtre les places libres selon :
    - price  : prix max en MAD/heure
    - time   : durée souhaitée en heures
    """
    max_price = int(request.GET.get("price", 50))
    duration  = int(request.GET.get("time", 1))

    try:
        spots = get_current_status()
    except Exception:
        spots = []

    results = [
        {**s, "total_cost": s["price"] * duration}
        for s in spots
        if s["status"] == "free" and s["price"] <= max_price
    ]
    return JsonResponse({"spots": results, "count": len(results)})


# ────────────────────────────────────────────────────────
# API — Historique depuis parking.db
# ────────────────────────────────────────────────────────
def history_api(request):
    """Retourne les 50 dernières sessions depuis parking.db"""
    try:
        logs = ParkingLog.objects.order_by('-id')[:50]
        data = [
            {
                "spot":     l.spot,
                "car_id":   l.car_id,
                "duration": l.duration,
                "price":    l.price,
            }
            for l in logs
        ]
    except Exception:
        data = []

    return JsonResponse({"history": data})