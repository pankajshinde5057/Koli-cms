# forms.py
from django import forms
from .models import Assets
from django_filters import FilterSet

class AssetForm(forms.ModelForm):
    class Meta:
        model = Assets
        fields = ['asset_name', 'asset_serial_No', 'asset_manufacturer', 'date_purchased', 'asset_image', 'asset_assignee']


class AssetsFilter(FilterSet):
    class Meta:
        model = Assets
        fields = {
            'asset_name': ['icontains'],
        }
