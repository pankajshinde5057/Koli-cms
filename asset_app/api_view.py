# asset_app/api_views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import Assets
from .serializers import AssetDetailSerializer
from django.shortcuts import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.authentication import SessionAuthentication,BasicAuthentication


class AssetDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [BasicAuthentication]

    def get(self, request, pk):
        asset = get_object_or_404(Assets, pk=pk)
        serializer = AssetDetailSerializer(asset)
        return Response(serializer.data, status=status.HTTP_200_OK)

