## services/views.py

from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from django.shortcuts import get_object_or_404
from .models import ServiceTier, ClientProject, Payment
from .serializers import ServiceTierSerializer, ClientProjectSerializer, PaymentSerializer
from users.models import User
from .tasks import process_payment_task, update_project_status_task
from django.db import transaction

class ServiceTierListView(generics.ListAPIView):
    queryset = ServiceTier.objects.all()
    serializer_class = ServiceTierSerializer
    permission_classes = [permissions.AllowAny]

class ClientProjectListCreateView(generics.ListCreateAPIView):
    serializer_class = ClientProjectSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return ClientProject.objects.filter(client=self.request.user)

    def perform_create(self, serializer):
        service_tier = get_object_or_404(ServiceTier, id=self.request.data.get('service_tier'))
        with transaction.atomic():
            project = serializer.save(client=self.request.user, service_tier=service_tier)
            Payment.objects.create(
                user=self.request.user,
                amount=service_tier.price,
                stripe_charge_id=f"temp_{project.id}",  # This will be updated by the payment processor
                status='pending'
            )
            process_payment_task.delay(project.id)

class ClientProjectDetailView(generics.RetrieveUpdateAPIView):
    serializer_class = ClientProjectSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return ClientProject.objects.filter(client=self.request.user)

class StartProjectView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        project = get_object_or_404(ClientProject, id=pk, client=request.user)
        if project.status == 'pending':
            project.start_project()
            return Response({'message': 'Project started successfully'}, status=status.HTTP_200_OK)
        return Response({'error': 'Project cannot be started'}, status=status.HTTP_400_BAD_REQUEST)

class UpdateProjectProgressView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        project = get_object_or_404(ClientProject, id=pk, client=request.user)
        step = request.data.get('step')
        status = request.data.get('status')
        if step and status:
            project.update_progress(step, status)
            update_project_status_task.delay(project.id)
            return Response({'message': 'Progress updated successfully'}, status=status.HTTP_200_OK)
        return Response({'error': 'Invalid data'}, status=status.HTTP_400_BAD_REQUEST)

class CompleteProjectView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        project = get_object_or_404(ClientProject, id=pk, client=request.user)
        if project.status == 'in_progress':
            project.complete_project()
            return Response({'message': 'Project completed successfully'}, status=status.HTTP_200_OK)
        return Response({'error': 'Project cannot be completed'}, status=status.HTTP_400_BAD_REQUEST)

class PaymentListView(generics.ListAPIView):
    serializer_class = PaymentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Payment.objects.filter(user=self.request.user)

class ProcessPaymentView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        payment = get_object_or_404(Payment, id=pk, user=request.user)
        if payment.status == 'pending':
            payment.process_payment()
            return Response({'message': 'Payment processed successfully'}, status=status.HTTP_200_OK)
        return Response({'error': 'Payment cannot be processed'}, status=status.HTTP_400_BAD_REQUEST)

class RefundPaymentView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        payment = get_object_or_404(Payment, id=pk, user=request.user)
        if payment.status == 'completed':
            payment.refund()
            return Response({'message': 'Payment refunded successfully'}, status=status.HTTP_200_OK)
        return Response({'error': 'Payment cannot be refunded'}, status=status.HTTP_400_BAD_REQUEST)
