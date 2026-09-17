from django import forms
from django.conf import settings
from .location_data import CATEGORY_CHOICES

class SearchForm(forms.Form):
    provider = forms.ChoiceField(choices=[("osm", "OpenStreetMap (Free)"), ("google", "Google Places (Paid)")])
    country = forms.CharField(max_length=100, strip=True)
    province = forms.CharField(max_length=150, required=False, strip=True)
    city = forms.CharField(max_length=100, strip=True)
    area = forms.CharField(max_length=150, required=False, strip=True)
    category = forms.ChoiceField(choices=CATEGORY_CHOICES)
    keyword = forms.CharField(max_length=150, required=False, strip=True)
    limit = forms.TypedChoiceField(coerce=int, choices=[(10, "10"), (20, "20"), (50, "50"), (100, "100")])

    def clean_limit(self):
        return min(self.cleaned_data["limit"], settings.MAX_RESULTS_PER_SEARCH)
