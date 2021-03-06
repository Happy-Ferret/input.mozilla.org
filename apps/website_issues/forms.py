from collections import namedtuple

from django import forms
from django.forms import (CharField, ChoiceField, BooleanField, HiddenInput,
                          IntegerField)

from tower import ugettext_lazy as _lazy

from input import PLATFORMS, PRODUCTS, FIREFOX, MOBILE
from input.fields import SearchInput
from search.forms import SENTIMENT_CHOICES, PLATFORM_CHOICES, PROD_CHOICES


VERSION_CHOICES = {
    FIREFOX: [(v, v) for v in FIREFOX.extra_versions +
                              FIREFOX.beta_versions +
                              FIREFOX.release_versions],
    MOBILE: [(v, v) for v in MOBILE.extra_versions +
                             MOBILE.beta_versions +
                             MOBILE.release_versions],
}

FieldDef = namedtuple("FieldDef", "default field keys")


def field_def(FieldType, default, widget=HiddenInput, choices=None):
    field_args = {"required": False, "label": "", "widget": widget}
    keys = None
    if choices is not None:
        field_args.update({"choices": choices})
        keys = set([key for key, value in choices])
    return FieldDef(default, FieldType(**field_args), keys)


FIELD_DEFS = {
    "q": field_def(
        CharField, "",
        widget=SearchInput(
            attrs={'placeholder': _lazy('Search for domain',
                                        'website_issues_search')}
        )
    ),
    "sentiment": field_def(ChoiceField, "", choices=SENTIMENT_CHOICES),
    "product": field_def(ChoiceField, FIREFOX.short, choices=PROD_CHOICES),
    "platform": field_def(ChoiceField, "", choices=PLATFORM_CHOICES),
    "show_one_offs": field_def(BooleanField, False),
    "page": field_def(IntegerField, 1),
    "site": field_def(IntegerField, None),
    "cluster": field_def(IntegerField, None)
}


class WebsiteIssuesSearchForm(forms.Form):

    # Fields that are submitted on text search:
    q = FIELD_DEFS['q'].field
    sentiment = FIELD_DEFS['sentiment'].field
    product = forms.ChoiceField(choices=PROD_CHOICES, label=_lazy('Product:'),
                            initial=FIREFOX.short, required=False)
    platform = FIELD_DEFS['platform'].field
    version = forms.ChoiceField(required=False, label=_lazy('Version:'),
                                choices=VERSION_CHOICES[FIREFOX])
    show_one_offs = FIELD_DEFS['show_one_offs'].field

    # These fields are reset on search:
    page = FIELD_DEFS['page'].field
    site = FIELD_DEFS['site'].field
    cluster = FIELD_DEFS['cluster'].field

    def __init__(self, *args, **kwargs):
        """Set available products/versions based on selected channel/product"""
        super(WebsiteIssuesSearchForm, self).__init__(*args, **kwargs)
        self.fields['version'].choices = VERSION_CHOICES[FIREFOX]
        picked = None
        if self.is_bound:
            try:
                picked = self.fields['product'].clean(self.data.get('product'))
            except forms.ValidationError:
                pass
        if (picked == MOBILE.short):
            # We default to Firefox. Only change if this is the mobile site.
            self.fields['product'].initial = MOBILE.short
            self.fields['version'].choices = VERSION_CHOICES[MOBILE]

    def clean(self):
        cleaned = super(WebsiteIssuesSearchForm, self).clean()

        for field_name, field_def in FIELD_DEFS.items():
            if field_name not in cleaned:
                cleaned[field_name] = field_def.default
                continue
            if BooleanField == type(field_def.field) \
                    and cleaned.get(field_name) not in (True, False):
                cleaned[field_name] = field_def.default
            if ChoiceField == type(field_def.field) \
                    and cleaned.get(field_name) not in field_def.keys:
                cleaned[field_name] = field_def.default

        if cleaned.get('product') and cleaned.get('platform'):
            product = PRODUCTS[cleaned.get('product')]
            possible_platforms = [platform for platform in PLATFORMS.values()
                                  if product in platform.prods]

            if PLATFORMS[cleaned.get('platform')] not in possible_platforms:
                cleaned['platform'] = FIELD_DEFS['platform'].default

        if not cleaned.get('version'):
            cleaned['version'] = (
                getattr(FIREFOX, 'default_version', None) or
                Version(LATEST_BETAS[FIREFOX]).simplified
            )

        if cleaned.get('page') is not None:
            cleaned['page'] = max(1, int(cleaned['page']))
        else:
            cleaned['page'] = FIELD_DEFS['page'].default

        return cleaned

    def full_clean(self):
        """Set cleaned data, with defaults for missing/invalid stuff."""
        super(WebsiteIssuesSearchForm, self).full_clean()
        try:
            return self.cleaned_data
        except AttributeError:
            self.cleaned_data = {}
            self.cleaned_data = self.clean()
            return self.cleaned_data
