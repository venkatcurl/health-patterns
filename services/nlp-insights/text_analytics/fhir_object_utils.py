# Copyright 2021 IBM All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Utilities for manipulating FHIR objects"""

import json

from fhir.resources.bundle import Bundle
from fhir.resources.bundle import BundleEntry, BundleEntryRequest
from fhir.resources.codeableconcept import CodeableConcept
from fhir.resources.coding import Coding
from fhir.resources.condition import Condition
from fhir.resources.extension import Extension
from fhir.resources.medicationstatement import MedicationStatement

import insight_constants


# FIXME: former create_coding_system_entry_with_extension
def create_coding(system, code, display=None, derived_by_nlp=False):
    """Creates an instance of a FHIR coding data type

       Args:
            system         - the url of the coding system
            code           - the code
            display        - the display text, if any
            derived_by_nlp - If true, a derived by NLP extension will be added

       Returns: coding element

       Examples:


        Code without display text:
        >>> code = create_coding("http://hl7.org/fhir/ValueSet/timing-abbreviation", "BID")
        >>> print(code.json(indent=2))
        {
          "code": "BID",
          "system": "http://hl7.org/fhir/ValueSet/timing-abbreviation"
        }


        Code with display text:
        >>> code = create_coding("http://hl7.org/fhir/ValueSet/timing-abbreviation","WK","weekly")
        >>> print(code.json(indent=2))
        {
          "code": "WK",
          "display": "weekly",
          "system": "http://hl7.org/fhir/ValueSet/timing-abbreviation"
        }


        Code derived by NLP:
        >>> code = create_coding("http://hl7.org/fhir/ValueSet/timing-abbreviation",
        ...                      "WK",
        ...                      derived_by_nlp=True)
        >>> print(code.json(indent=2))
        {
          "extension": [
            {
              "url": "http://ibm.com/fhir/cdm/StructureDefinition/category",
              "valueCodeableConcept": {
                "coding": [
                  {
                    "code": "natural-language-processing",
                    "display": "NLP",
                    "system": "http://ibm.com/fhir/cdm/CodeSystem/insight-category-code-system"
                  }
                ],
                "text": "NLP"
              }
            }
          ],
          "code": "WK",
          "system": "http://hl7.org/fhir/ValueSet/timing-abbreviation"
        }
    """
    coding_element = Coding.construct()
    coding_element.system = system
    coding_element.code = code

    if display:
        coding_element.display = display

    if derived_by_nlp:
        coding_element.extension = [create_derived_by_nlp_extension()]

    return coding_element


def create_confidence(name, value):
    """Creates a FHIR extension element for insight confidence

       Example:
        >>> print(create_confidence('insight', 1.0).json(indent=2))
        {
          "extension": [
            {
              "url": "http://ibm.com/fhir/cdm/StructureDefinition/description",
              "valueString": "insight"
            },
            {
              "url": "http://ibm.com/fhir/cdm/StructureDefinition/score",
              "valueString": "1.0"
            }
          ],
          "url": "http://ibm.com/fhir/cdm/StructureDefinition/insight-confidence"
        }
    """
    confidence = Extension.construct()
    confidence.url = insight_constants.INSIGHT_CONFIDENCE_URL

    confidence_name = Extension.construct()
    confidence_name.url = insight_constants.INSIGHT_CONFIDENCE_NAME_URL
    confidence_name.valueString = name

    confidence_score = Extension.construct()
    confidence_score.url = insight_constants.INSIGHT_CONFIDENCE_SCORE_URL
    confidence_score.valueString = value

    confidence.extension = [confidence_name]
    confidence.extension.append(confidence_score)
    return confidence


def create_derived_by_nlp_extension():
    """
    Creates an extension indicating the resource is derived from NLP

    Example:
    >>> print(create_derived_by_nlp_extension().json(indent=2))
    {
      "url": "http://ibm.com/fhir/cdm/StructureDefinition/category",
      "valueCodeableConcept": {
        "coding": [
          {
            "code": "natural-language-processing",
            "display": "NLP",
            "system": "http://ibm.com/fhir/cdm/CodeSystem/insight-category-code-system"
          }
        ],
        "text": "NLP"
      }
    }
    """
    classification_ext = Extension.construct()
    classification_ext.url = insight_constants.INSIGHT_CATEGORY_URL
    classification_coding = create_coding(insight_constants.CLASSIFICATION_DERIVED_SYSTEM,
                                          insight_constants.CLASSIFICATION_DERIVED_CODE,
                                          insight_constants.CLASSIFICATION_DERIVED_DISPLAY)
    classification_value = CodeableConcept.construct()
    classification_value.coding = [classification_coding]
    classification_value.text = insight_constants.CLASSIFICATION_DERIVED_DISPLAY
    classification_ext.valueCodeableConcept = classification_value
    return classification_ext


def append_derived_by_nlp_extension(resource):  # formerly create_derived_resource_extension
    """Append resource-level extension to resource, indicating resource was derived

       Does not check if the resource already exists

       Args:
            resource - entire resource created from insights

       Example:
       Prior medication resource:
        >>> resource_json = json.loads('''
        ... {
        ...    "medicationCodeableConcept": {
        ...      "coding": [
        ...             {
        ...                 "code": "C0025598",
        ...                 "display": "Metformin",
        ...                 "system": "http://terminology.hl7.org/CodeSystem/umls"
        ...             }
        ...      ],
        ...      "text": "Metformin"
        ...    },
        ...    "status": "unknown",
        ...    "subject": {
        ...      "reference": "Patient/7c33b82a-4efc-4082-9fe9-8122d6791552"
        ...    },
        ...    "resourceType": "MedicationStatement"
        ... }''')

        >>> resource = MedicationStatement.parse_obj(resource_json)

        Function Call:
        >>> append_derived_by_nlp_extension(resource)

        Updated Resource:
        >>> print(resource.json(indent=2))
        {
          "extension": [
            {
              "url": "http://ibm.com/fhir/cdm/StructureDefinition/category",
              "valueCodeableConcept": {
                "coding": [
                  {
                    "code": "natural-language-processing",
                    "display": "NLP",
                    "system": "http://ibm.com/fhir/cdm/CodeSystem/insight-category-code-system"
                  }
                ],
                "text": "NLP"
              }
            }
          ],
          "medicationCodeableConcept": {
            "coding": [
              {
                "code": "C0025598",
                "display": "Metformin",
                "system": "http://terminology.hl7.org/CodeSystem/umls"
              }
            ],
            "text": "Metformin"
          },
          "status": "unknown",
          "subject": {
            "reference": "Patient/7c33b82a-4efc-4082-9fe9-8122d6791552"
          },
          "resourceType": "MedicationStatement"
        }
    """
    classification_ext = create_derived_by_nlp_extension()
    if resource.extension is None:
        resource.extension = [classification_ext]
    else:
        resource.extension.append(classification_ext)


# fhir_resource_action --> list of resource(s) with their request type ('POST' or 'PUT') and url
#                    example: [[resource1, 'POST', 'url1'], [resource2, 'PUT', 'url2']]
def create_transaction_bundle(resource_action_list):
    """Creates a bundle from a list of resource tuples

        Args:
            resource_action_list - list of tuples of the form (resource, method_str, url_str)

        Example:
        
        Build input list:
        >>> condition1 = Condition.parse_obj(json.loads(
        ... '''
        ... {
        ...     "code": {
        ...         "text": "Diabetes Mellitus, Insulin-Dependent"
        ...     },
        ...     "subject": {
        ...         "reference": "Patient/7c33b82a-4efc-4082-9fe9-8122d6791552"
        ...     },
        ...     "resourceType": "Condition"
        ... }'''))
        
        >>> condition2 = Condition.parse_obj(json.loads(
        ... '''
        ... {
        ...     "code": {
        ...         "text": "Something else"
        ...     },
        ...     "subject": {
        ...         "reference": "Patient/7c33b82a-4efc-4082-9fe9-8122d6791552"
        ...     },
        ...     "resourceType": "Condition"
        ... }'''))
        
        Result:
        >>> bundle = create_transaction_bundle([(condition1, 'POST', 'http://url1'),
        ...                                     (condition2, 'POST', 'http://url2')])
        >>> print(bundle.json(indent=2))
        {
          "entry": [
            {
              "request": {
                "method": "POST",
                "url": "http://url1"
              },
              "resource": {
                "code": {
                  "text": "Diabetes Mellitus, Insulin-Dependent"
                },
                "subject": {
                  "reference": "Patient/7c33b82a-4efc-4082-9fe9-8122d6791552"
                },
                "resourceType": "Condition"
              }
            },
            {
              "request": {
                "method": "POST",
                "url": "http://url2"
              },
              "resource": {
                "code": {
                  "text": "Something else"
                },
                "subject": {
                  "reference": "Patient/7c33b82a-4efc-4082-9fe9-8122d6791552"
                },
                "resourceType": "Condition"
              }
            }
          ],
          "type": "transaction",
          "resourceType": "Bundle"
        }
        
        
    """
    bundle = Bundle.construct()
    bundle.type = "transaction"
    bundle.entry = []

    for resource, request_type, url in resource_action_list:
        bundle_entry = BundleEntry.construct()
        bundle_entry.resource = resource
        request = BundleEntryRequest.parse_obj(
            {
                "method": request_type,
                "url": url
            })
        bundle_entry.request = request
        bundle.entry.append(bundle_entry)

    return bundle
