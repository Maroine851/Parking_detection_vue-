from django.urls import path
from . import views

urlpatterns = [
    path('',            views.dashboard,   name='dashboard'),
    path('video/',      views.video_feed,  name='video_feed'),
    path('live-stats/', views.live_stats,  name='live_stats'),
    path('search/',     views.search_spots, name='search_spots'),
    path('history/',    views.history_api,  name='history_api'),
]