from django.contrib import admin
from .models import (Task, Profile, LearningPlan, Phase, Module, Lesson, Goal,
    Milestone, FocusSession, Revision, JobApplication, PracticeEntry)
admin.site.register([Task, Profile, LearningPlan, Phase, Module, Lesson, Goal,
    Milestone, FocusSession, Revision, JobApplication, PracticeEntry])
