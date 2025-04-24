# forms.py
from django import forms
from .models import Assets, AssetCategory
from django_filters import FilterSet


class AssetCategoryForm(forms.ModelForm):
    class Meta:
        model = AssetCategory
        fields = ['category']


class AssetForm(forms.ModelForm):
    class Meta:
        model = Assets
        fields = [
            'asset_category',
            'asset_name',
            'asset_serial_number',
            'asset_brand',        
            'asset_image',
            'is_asset_issued',
            'asset_condition',
            'os_version',
            'ip_address',
            'return_date',
            'barcode'
        ]

class AssetsFilter(FilterSet):
    class Meta:
        model = Assets
        fields = {
            'asset_name': ['icontains'],
        }
