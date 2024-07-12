## church_formation_project/urls.py

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

urlpatterns = [
    # Admin
    path('admin/', admin.site.urls),

    # API endpoints
    path('api/', include([
        # Users app
        path('users/', include('users.urls')),

        # Services app
        path('services/', include('services.urls')),

        # Resources app
        path('resources/', include('resources.urls')),

        # Consultants app
        path('consultants/', include('consultants.urls')),

        # JWT authentication
        path('token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
        path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    ])),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# Custom 404 and 500 error handlers
handler404 = 'church_formation_project.views.custom_404'
handler500 = 'church_formation_project.views.custom_500'
