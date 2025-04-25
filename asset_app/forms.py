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
        ]
    
    # def __init__(self, *args, **kwargs):
    #     super().__init__(*args, **kwargs)
    #     if self.instance.pk:
    #         self.fields['asset_serial_number'].required = False
    
    # def clean_asset_serial_number(self):
    #     serial_number = self.cleaned_data.get('asset_serial_number')
    #     if not serial_number and self.instance.pk:
    #         return self.instance.asset_serial_number
    #     return serial_number

class AssetsFilter(FilterSet):
    class Meta:
        model = Assets
        fields = {
            'asset_name': ['icontains'],
        }
