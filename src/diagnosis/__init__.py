"""Rule-based diagnosis of stored runs (docs/DIAGNOSIS.md). No model is called by anything in this package unless a
backend is chosen explicitly (src/diagnosis/backends.py)."""

from src.diagnosis.schema import DiagnosisInput, LogLine, load_diagnosis_input

__all__ = ["DiagnosisInput", "LogLine", "load_diagnosis_input"]
