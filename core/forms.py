from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import get_user_model
from .models import (Task, Profile, LearningPlan, Phase, Module, Lesson, Goal,
    Milestone, FocusSession, JobApplication, Revision, PracticeEntry)
class TaskForm(forms.ModelForm):
    class Meta:
        model = Task
        fields = ["title", "subject", "phase", "priority", "scheduled_date", "est_minutes", "reminder_at", "description", "resource"]
        widgets = {"scheduled_date": forms.DateInput(attrs={"type": "date"}), "reminder_at": forms.DateTimeInput(attrs={"type":"datetime-local"}), "description": forms.Textarea(attrs={"rows": 2})}
class SettingsForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ["display_name", "timezone", "daily_target_minutes", "preferred_study_days", "weekly_review_day", "show_briefing", "notifications_enabled"]
    def clean_timezone(self):
        from zoneinfo import ZoneInfo
        v = self.cleaned_data["timezone"]
        try: ZoneInfo(v)
        except Exception: raise forms.ValidationError("Unknown timezone, e.g. Asia/Karachi")
        return v
class RegisterForm(UserCreationForm):
    email = forms.EmailField(required=True)
    class Meta(UserCreationForm.Meta):
        model = get_user_model()
        fields = ("username", "email", "password1", "password2")

class AccountEmailForm(forms.ModelForm):
    class Meta:
        model = get_user_model()
        fields = ["email"]

class LearningPlanForm(forms.ModelForm):
    class Meta:
        model = LearningPlan
        fields = ["title", "description", "start_date", "target_date", "status", "is_template"]
        widgets = {"start_date": forms.DateInput(attrs={"type":"date"}), "target_date": forms.DateInput(attrs={"type":"date"})}
class PhaseForm(forms.ModelForm):
    class Meta: model = Phase; fields = ["title", "position"]
class ModuleForm(forms.ModelForm):
    class Meta: model = Module; fields = ["title", "description", "position"]
class LessonForm(forms.ModelForm):
    class Meta: model = Lesson; fields = ["title", "description", "resource", "est_minutes", "position"]
class GoalForm(forms.ModelForm):
    class Meta:
        model = Goal; fields = ["title", "description", "target_date", "priority", "status"]
        widgets = {"target_date": forms.DateInput(attrs={"type":"date"})}
class MilestoneForm(forms.ModelForm):
    class Meta:
        model = Milestone; fields = ["title", "due_date", "position"]
        widgets = {"due_date": forms.DateInput(attrs={"type":"date"})}
class FocusSessionForm(forms.ModelForm):
    class Meta:
        model = FocusSession; fields = ["task", "started_at", "ended_at", "notes"]
        widgets = {"started_at": forms.DateTimeInput(attrs={"type":"datetime-local"}), "ended_at": forms.DateTimeInput(attrs={"type":"datetime-local"})}
    def __init__(self, *args, owner=None, **kwargs):
        super().__init__(*args, **kwargs)
        if owner is not None: self.fields["task"].queryset = Task.objects.filter(user=owner)
    def clean(self):
        data = super().clean()
        start, end = data.get("started_at"), data.get("ended_at")
        if start and end and end <= start: self.add_error("ended_at", "End time must be after start time.")
        return data
class RevisionForm(forms.ModelForm):
    class Meta:
        model = Revision; fields = ["due_date"]
        widgets = {"due_date": forms.DateInput(attrs={"type":"date"})}
class JobApplicationForm(forms.ModelForm):
    class Meta:
        model = JobApplication; fields = ["company", "role", "url", "applied_on", "status", "notes"]
        widgets = {"applied_on": forms.DateInput(attrs={"type":"date"})}
class PracticeEntryForm(forms.ModelForm):
    class Meta:
        model = PracticeEntry; fields = ["kind", "title", "platform", "resource", "outcome", "notes", "happened_at"]
        widgets = {"happened_at": forms.DateTimeInput(attrs={"type":"datetime-local"}), "notes": forms.Textarea(attrs={"rows":2})}

class TaskImportForm(forms.Form):
    file = forms.FileField(help_text="JSON exported from ProgressPilot; maximum size 5 MB.")
    def clean_file(self):
        f=self.cleaned_data["file"]
        if f.size > 5 * 1024 * 1024: raise forms.ValidationError("File must be 5 MB or smaller.")
        if not f.name.lower().endswith(".json"): raise forms.ValidationError("Choose a .json file.")
        return f
