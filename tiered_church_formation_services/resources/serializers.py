## resources/serializers.py

from rest_framework import serializers
from .models import Resource, ResourceRating, ResourceCategory, ResourceCategoryAssignment
from users.serializers import UserSerializer

class ResourceCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ResourceCategory
        fields = ['id', 'name', 'description', 'parent']

class ResourceSerializer(serializers.ModelSerializer):
    created_by = UserSerializer(read_only=True)
    categories = ResourceCategorySerializer(many=True, read_only=True, source='category_assignments.category')

    class Meta:
        model = Resource
        fields = ['id', 'title', 'description', 'file_type', 'file_url', 'tags', 'is_premium', 'created_at', 'updated_at', 'created_by', 'categories']
        read_only_fields = ['id', 'created_at', 'updated_at', 'created_by']

    def create(self, validated_data):
        categories_data = self.context.get('request').data.get('categories', [])
        resource = Resource.objects.create(**validated_data)
        for category_id in categories_data:
            category = ResourceCategory.objects.get(id=category_id)
            ResourceCategoryAssignment.objects.create(resource=resource, category=category)
        return resource

    def update(self, instance, validated_data):
        categories_data = self.context.get('request').data.get('categories', [])
        instance = super().update(instance, validated_data)
        instance.category_assignments.all().delete()
        for category_id in categories_data:
            category = ResourceCategory.objects.get(id=category_id)
            ResourceCategoryAssignment.objects.create(resource=instance, category=category)
        return instance

class ResourceDetailSerializer(ResourceSerializer):
    average_rating = serializers.FloatField(read_only=True)
    user_rating = serializers.SerializerMethodField()

    class Meta(ResourceSerializer.Meta):
        fields = ResourceSerializer.Meta.fields + ['average_rating', 'user_rating']

    def get_user_rating(self, obj):
        user = self.context['request'].user
        try:
            rating = ResourceRating.objects.get(user=user, resource=obj)
            return rating.rating
        except ResourceRating.DoesNotExist:
            return None

class ResourceRatingSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)

    class Meta:
        model = ResourceRating
        fields = ['id', 'user', 'resource', 'rating', 'comment', 'created_at', 'updated_at']
        read_only_fields = ['id', 'user', 'resource', 'created_at', 'updated_at']

    def validate_rating(self, value):
        if value < 1 or value > 5:
            raise serializers.ValidationError("Rating must be between 1 and 5.")
        return value

class ResourceCategoryDetailSerializer(ResourceCategorySerializer):
    children = ResourceCategorySerializer(many=True, read_only=True)

    class Meta(ResourceCategorySerializer.Meta):
        fields = ResourceCategorySerializer.Meta.fields + ['children']

class ResourceSearchSerializer(serializers.Serializer):
    query = serializers.CharField(required=True, max_length=100)

class ResourceStatsSerializer(serializers.Serializer):
    access_count = serializers.IntegerField()
    average_rating = serializers.FloatField()

class RecommendedResourceSerializer(ResourceSerializer):
    relevance_score = serializers.FloatField()

    class Meta(ResourceSerializer.Meta):
        fields = ResourceSerializer.Meta.fields + ['relevance_score']

class ResourceUploadSerializer(ResourceSerializer):
    file = serializers.FileField(write_only=True)

    class Meta(ResourceSerializer.Meta):
        fields = ResourceSerializer.Meta.fields + ['file']

    def create(self, validated_data):
        file = validated_data.pop('file', None)
        resource = super().create(validated_data)
        if file:
            resource.file_url.save(file.name, file, save=True)
        return resource

class ResourceUpdateSerializer(ResourceSerializer):
    file = serializers.FileField(write_only=True, required=False)

    class Meta(ResourceSerializer.Meta):
        fields = ResourceSerializer.Meta.fields + ['file']

    def update(self, instance, validated_data):
        file = validated_data.pop('file', None)
        instance = super().update(instance, validated_data)
        if file:
            instance.file_url.save(file.name, file, save=True)
        return instance
