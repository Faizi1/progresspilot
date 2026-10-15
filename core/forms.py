from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import Task, Profile
class TaskForm(forms.ModelForm):
    class Meta:
        model = Task
        fields = ["title", "subject", "priority", "scheduled_date", "est_minutes", "description", "resource"]
        widgets = {"scheduled_date": forms.DateInput(attrs={"type": "date"}), "description": forms.Textarea(attrs={"rows": 2})}
class SettingsForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ["timezone", "show_briefing"]
    def clean_timezone(self):
        from zoneinfo import ZoneInfo
        v = self.cleaned_data["timezone"]
        try: ZoneInfo(v)
        except Exception: raise forms.ValidationError("Unknown timezone, e.g. Asia/Karachi")
        return v
RegisterForm = UserCreationForm
