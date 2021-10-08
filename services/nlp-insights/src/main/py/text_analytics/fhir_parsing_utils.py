"""
Utilities for parsing fhir resources into objects
"""
import json
from json.decoder import JSONDecodeError
from typing import Callable
from typing import Dict
from typing import Type
from typing import TypeVar

from fhir.resources.allergyintolerance import AllergyIntolerance
from fhir.resources.bundle import Bundle
from fhir.resources.condition import Condition
from fhir.resources.diagnosticreport import DiagnosticReport
from fhir.resources.documentreference import DocumentReference
from fhir.resources.medicationstatement import MedicationStatement
from fhir.resources.resource import Resource
from pydantic import ValidationError
from werkzeug.exceptions import BadRequest
from werkzeug.wrappers import Response


def parse_fhir_resource_from_payload(doc: str) -> Resource:
    """Parses user provided json into an object

       Args: doc - the json document string
       Returns: Fhir Resource

    raises BadRequest if the provided data is not valid
    """
    T = TypeVar("T", bound=Resource)
    parsers: Dict[str, Callable[[Type[T]], T]] = {
        "Bundle": Bundle.parse_obj,
        "MedicationStatement": MedicationStatement.parse_obj,
        "Condition": Condition.parse_obj,
        "DocumentReference": DocumentReference.parse_obj,
        "DiagnosticReport": DiagnosticReport.parse_obj,
        "AllergyIntolerance": AllergyIntolerance.parse_obj,
    }

    try:
        obj = json.loads(doc)
    except JSONDecodeError as jderr:
        raise BadRequest(
            response=Response(
                "Resource was not valid json = " + str(jderr), content_type="text/plain"
            )
        ) from jderr

    if "resourceType" in obj and obj["resourceType"] in parsers:
        try:
            return parsers[obj["resourceType"]](obj)
        except ValidationError as verr:
            raise BadRequest(
                response=Response(verr.json(), content_type="application/json")
            ) from verr

    else:
        raise BadRequest(
            response=Response(
                "Payload does not have a fhir resourceType or the resource type is not supported"
            )
        )
