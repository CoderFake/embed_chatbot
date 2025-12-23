"""Common enums for visitor-grader service."""
from enum import Enum


class TaskType(str, Enum):
    """Task types for visitor grading/assessment."""
    GRADING = "grading"
    ASSESSMENT = "assessment"


class LeadCategory(str, Enum):
    """Lead quality categories."""
    HOT = "hot"
    WARM = "warm"
    COLD = "cold"

