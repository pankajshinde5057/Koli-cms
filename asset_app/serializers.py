from rest_framework import serializers
from .models import Assets

class AssetDetailSerializer(serializers.ModelSerializer):
    asset_assignee_name = serializers.SerializerMethodField()
    manager_name = serializers.SerializerMethodField()
    status = serializers.ReadOnlyField()

    class Meta:
        model = Assets
        fields = [
            'id',
            'asset_name',
            'asset_serial_No',
            'asset_manufacturer',
            'date_purchased',
            'asset_issued',
            'asset_image',
            'qr_code',
            'status',
            'asset_assignee_name',
            'manager_name'
        ]

    def get_asset_assignee_name(self, obj):
        return obj.asset_assignee.get_full_name() if obj.asset_assignee else None

    def get_manager_name(self, obj):
        return obj.manager.get_full_name() if obj.manager else None