# forms.py
from django import forms
from .models import Assets
from django_filters import FilterSet

class AssetForm(forms.ModelForm):
    class Meta:
        model = Assets
        fields = [
            'asset_name',
            'asset_serial_No',
            'asset_brand',        
            'asset_image',
            'is_asset_issued',
            'asset_condition',
            'os_version',
            'ip_address',
            'return_date',
        ]

class AssetsFilter(FilterSet):
    class Meta:
        model = Assets
        fields = {
            'asset_name': ['icontains'],
        }
