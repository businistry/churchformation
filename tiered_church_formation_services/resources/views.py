## resources/views.py

from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from django.shortcuts import get_object_or_404
from django.db.models import Avg, Q, Count
from .models import Resource, ResourceAccess, ResourceRating, ResourceCategory
from .serializers import (
    ResourceSerializer,
    ResourceDetailSerializer,
    ResourceRatingSerializer,
    ResourceCategorySerializer,
)
from services.models import ClientProject
from django.core.exceptions import PermissionDenied
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from django.core.cache import cache

class ResourceListView(generics.ListAPIView):
    serializer_class = ResourceSerializer
    permission_classes = [permissions.IsAuthenticated]

    @method_decorator(cache_page(60 * 15))  # Cache for 15 minutes
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    def get_queryset(self):
        user = self.request.user
        queryset = Resource.objects.all().select_related('created_by').prefetch_related('category_assignments__category')

        # Apply filters
        category = self.request.query_params.get('category')
        tags = self.request.query_params.get('tags')
        file_type = self.request.query_params.get('file_type')

        if category:
            queryset = queryset.filter(category_assignments__category__name=category)
        if tags:
            queryset = queryset.filter(tags__contains=tags.split(','))
        if file_type:
            queryset = queryset.filter(file_type=file_type)

        # Check user's access to premium resources
        if not user.is_staff:
            active_projects = ClientProject.objects.filter(client=user, status='in_progress').exists()
            if active_projects:
                queryset = queryset.filter(Q(is_premium=False) | Q(is_premium=True))
            else:
                queryset = queryset.filter(is_premium=False)

        return queryset.distinct()

class ResourceDetailView(generics.RetrieveAPIView):
    serializer_class = ResourceDetailSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = Resource.objects.all()

    @method_decorator(cache_page(60 * 5))  # Cache for 5 minutes
    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        user = request.user

        if instance.is_premium and not user.is_staff:
            active_projects = ClientProject.objects.filter(client=user, status='in_progress').exists()
            if not active_projects:
                raise PermissionDenied("You don't have access to this premium resource.")

        ResourceAccess.objects.get_or_create(user=user, resource=instance)

        serializer = self.get_serializer(instance)
        return Response(serializer.data)

class ResourceRatingCreateView(generics.CreateAPIView):
    serializer_class = ResourceRatingSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        resource = get_object_or_404(Resource, pk=self.kwargs['pk'])
        serializer.save(user=self.request.user, resource=resource)
        cache.delete(f'resource_stats_{resource.pk}')

class ResourceRatingUpdateView(generics.UpdateAPIView):
    serializer_class = ResourceRatingSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = ResourceRating.objects.select_related('resource')

    def perform_update(self, serializer):
        serializer.save()
        cache.delete(f'resource_stats_{serializer.instance.resource.pk}')

class ResourceCategoryListView(generics.ListAPIView):
    serializer_class = ResourceCategorySerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = ResourceCategory.objects.filter(parent=None).prefetch_related('children')

    @method_decorator(cache_page(60 * 60))  # Cache for 1 hour
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

class ResourceSearchView(generics.ListAPIView):
    serializer_class = ResourceSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        query = self.request.query_params.get('q', '')
        return Resource.objects.filter(
            Q(title__icontains=query) | 
            Q(description__icontains=query) |
            Q(tags__contains=[query])
        ).distinct()

class ResourceStatsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk):
        cache_key = f'resource_stats_{pk}'
        stats = cache.get(cache_key)

        if not stats:
            resource = get_object_or_404(Resource, pk=pk)
            stats = {
                'access_count': ResourceAccess.objects.filter(resource=resource).count(),
                'average_rating': ResourceRating.objects.filter(resource=resource).aggregate(Avg('rating'))['rating__avg']
            }
            cache.set(cache_key, stats, 60 * 5)  # Cache for 5 minutes

        return Response(stats)

class UserResourceAccessListView(generics.ListAPIView):
    serializer_class = ResourceSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        return Resource.objects.filter(user_accesses__user=user).distinct()

class RecommendedResourcesView(generics.ListAPIView):
    serializer_class = ResourceSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        accessed_resources = ResourceAccess.objects.filter(user=user).values_list('resource', flat=True)
        user_tags = Resource.objects.filter(id__in=accessed_resources).values_list('tags', flat=True)
        
        user_tags = set(tag for tags in user_tags for tag in tags)
        
        return Resource.objects.exclude(id__in=accessed_resources)\
            .filter(tags__overlap=list(user_tags))\
            .annotate(tag_count=Count('tags'))\
            .order_by('-tag_count', '-created_at')\
            .distinct()[:10]

class ResourceUploadView(generics.CreateAPIView):
    serializer_class = ResourceSerializer
    permission_classes = [permissions.IsAdminUser]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

class ResourceUpdateView(generics.UpdateAPIView):
    serializer_class = ResourceSerializer
    permission_classes = [permissions.IsAdminUser]
    queryset = Resource.objects.all()

    def perform_update(self, serializer):
        serializer.save()
        cache.delete(f'resource_stats_{serializer.instance.pk}')

class ResourceDeleteView(generics.DestroyAPIView):
    permission_classes = [permissions.IsAdminUser]
    queryset = Resource.objects.all()

    def perform_destroy(self, instance):
        cache.delete(f'resource_stats_{instance.pk}')
        instance.delete()
