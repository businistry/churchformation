## services/serializers.py

from rest_framework import serializers
from .models import ServiceTier, ClientProject, Payment
from users.serializers import UserSerializer

class ServiceTierSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServiceTier
        fields = ['id', 'name', 'description', 'price', 'is_full_service', 'features']

class ClientProjectSerializer(serializers.ModelSerializer):
    client = UserSerializer(read_only=True)
    service_tier = ServiceTierSerializer(read_only=True)
    service_tier_id = serializers.PrimaryKeyRelatedField(
        queryset=ServiceTier.objects.all(),
        source='service_tier',
        write_only=True
    )

    class Meta:
        model = ClientProject
        fields = ['id', 'client', 'service_tier', 'service_tier_id', 'project_name', 'start_date', 'status', 'progress']
        read_only_fields = ['id', 'client', 'start_date', 'status', 'progress']

    def create(self, validated_data):
        user = self.context['request'].user
        return ClientProject.objects.create(client=user, **validated_data)

    def update(self, instance, validated_data):
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance

class PaymentSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)

    class Meta:
        model = Payment
        fields = ['id', 'user', 'amount', 'stripe_charge_id', 'timestamp', 'status']
        read_only_fields = ['id', 'user', 'stripe_charge_id', 'timestamp', 'status']

    def create(self, validated_data):
        user = self.context['request'].user
        return Payment.objects.create(user=user, **validated_data)

class ProjectProgressUpdateSerializer(serializers.Serializer):
    step = serializers.CharField(required=True)
    status = serializers.CharField(required=True)

class PaymentProcessSerializer(serializers.Serializer):
    stripe_token = serializers.CharField(required=True)

class RefundRequestSerializer(serializers.Serializer):
    reason = serializers.CharField(required=True, max_length=255)

class ServiceTierDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServiceTier
        fields = ['id', 'name', 'description', 'price', 'is_full_service', 'features']

class ClientProjectDetailSerializer(serializers.ModelSerializer):
    client = UserSerializer(read_only=True)
    service_tier = ServiceTierDetailSerializer(read_only=True)
    payments = PaymentSerializer(many=True, read_only=True)

    class Meta:
        model = ClientProject
        fields = ['id', 'client', 'service_tier', 'project_name', 'start_date', 'status', 'progress', 'payments']
        read_only_fields = ['id', 'client', 'service_tier', 'start_date', 'status', 'progress', 'payments']

class PaymentDetailSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    project = ClientProjectSerializer(read_only=True)

    class Meta:
        model = Payment
        fields = ['id', 'user', 'project', 'amount', 'stripe_charge_id', 'timestamp', 'status']
        read_only_fields = ['id', 'user', 'project', 'stripe_charge_id', 'timestamp', 'status']
