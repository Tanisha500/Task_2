"""Flask REST API for the React Health Prediction Application."""

from functools import lru_cache
import os

from flask import Flask, jsonify, request
from flask_cors import CORS

from database import (all_patients, delete_patient, get_patient, initialize,
                      rejected_assignment_rows, save_patient)
from groq_service import format_assessment
from medlineplus import create_remarks, get_medlineplus_topics
from validation import validate_patient

app = Flask(__name__)
CORS(app, resources={
    r"/api/*": {"origins": os.getenv("FRONTEND_ORIGIN", "http://localhost:5173")}
})

initialize()


@lru_cache(maxsize=256)
def _display_remarks(glucose, haemoglobin, cholesterol, stored_remarks):
    """Refresh legacy remarks for display without changing the stored SQLite row."""
    formatted = format_assessment(stored_remarks, glucose, haemoglobin, cholesterol)
    if formatted:
        return formatted
    return create_remarks(glucose, haemoglobin, cholesterol)


def _patient_for_api(patient):
    patient = dict(patient)
    patient["remarks"] = _display_remarks(
        patient["glucose"], patient["haemoglobin"], patient["cholesterol"], patient["remarks"])
    return patient


def _validation_error(errors):
    return jsonify({"error": "Please correct the highlighted fields.", "fields": errors}), 400


def _request_data():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return None
    return data


@app.get("/api/health")
def health():
    return jsonify({"status": "ok"})


@app.get("/api/patients")
def list_patients():
    return jsonify({"patients": [_patient_for_api(row) for row in all_patients()]})


@app.get("/api/patients/<int:patient_id>")
def read_patient(patient_id):
    patient = get_patient(patient_id)
    if patient is None:
        return jsonify({"error": "Patient record not found."}), 404
    return jsonify({"patient": _patient_for_api(patient)})


@app.post("/api/patients")
def create_patient():
    data = _request_data()
    if data is None:
        return jsonify({"error": "Send patient fields as a JSON object."}), 400
    patient, errors = validate_patient(data)
    if errors:
        return _validation_error(errors)
    remarks = create_remarks(patient["glucose"], patient["haemoglobin"], patient["cholesterol"])
    save_patient(patient, remarks)
    return jsonify({"message": "Patient record created.", "patient": all_patients()[-1]}), 201


@app.put("/api/patients/<int:patient_id>")
def update_patient(patient_id):
    existing = get_patient(patient_id)
    if existing is None:
        return jsonify({"error": "Patient record not found."}), 404
    data = _request_data()
    if data is None:
        return jsonify({"error": "Send patient fields as a JSON object."}), 400
    keep_seed_date = (data.get("date_of_birth") == existing["date_of_birth"]
                      and "." in existing["date_of_birth"])
    patient, errors = validate_patient(data, assignment_date_format=keep_seed_date)
    if errors:
        return _validation_error(errors)
    remarks = create_remarks(patient["glucose"], patient["haemoglobin"], patient["cholesterol"])
    save_patient(patient, remarks, patient_id)
    return jsonify({"message": "Patient record updated.", "patient": get_patient(patient_id)})


@app.delete("/api/patients/<int:patient_id>")
def remove_patient(patient_id):
    if get_patient(patient_id) is None:
        return jsonify({"error": "Patient record not found."}), 404
    delete_patient(patient_id)
    return jsonify({"message": "Patient record deleted."})


@app.get("/api/assignment/rejected")
def list_rejected_assignment_rows():
    return jsonify({"records": rejected_assignment_rows()})


@app.get("/api/medlineplus")
def medlineplus_references():
    return jsonify({"topics": get_medlineplus_topics()})


@app.errorhandler(404)
def not_found(_error):
    return jsonify({"error": "The requested API route was not found."}), 404


@app.errorhandler(500)
def internal_error(_error):
    return jsonify({"error": "The server could not complete the request."}), 500


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.getenv("PORT", "5000")), debug=False)
