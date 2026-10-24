from django.db import transaction
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import Event, Reservation
from .serializers import EventSerializer, ReservationSerializer


class EventViewSet(viewsets.ModelViewSet):
    serializer_class = EventSerializer

    def get_queryset(self):
        queryset = Event.objects.all()
        status_param = self.request.query_params.get('status')
        venue_param = self.request.query_params.get('venue')

        if status_param:
            queryset = queryset.filter(status=status_param)
        if venue_param:
            queryset = queryset.filter(venue__icontains=venue_param)
        return queryset


class ReservationViewSet(viewsets.ModelViewSet):
    serializer_class = ReservationSerializer
    # no PUT/PATCH - editing seats_reserved directly would not update the
    # event's available_seats. To change a booking, cancel it and book again.
    http_method_names = ['get', 'post', 'delete', 'head', 'options']

    def get_queryset(self):
        queryset = Reservation.objects.all()
        event_id = self.request.query_params.get('event_id')

        if event_id:
            queryset = queryset.filter(event_id=event_id)
        return queryset

    # detail=True means URL is /reservations/{id}/cancel/
    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        reservation = self.get_object()

        if reservation.status == 'cancelled':
            return Response({'error': 'Already cancelled.'}, status=400)

        with transaction.atomic():
            event = Event.objects.select_for_update().get(pk=reservation.event_id)
            event.available_seats += reservation.seats_reserved
            event.save()

            reservation.status = 'cancelled'
            reservation.save()

        return Response(self.get_serializer(reservation).data)

    def perform_destroy(self, instance):
        # give the seats back if a confirmed reservation is deleted
        with transaction.atomic():
            if instance.status == 'confirmed':
                event = Event.objects.select_for_update().get(pk=instance.event_id)
                event.available_seats += instance.seats_reserved
                event.save()
            instance.delete()
