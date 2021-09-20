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
"""Utilities for building and manipulating FHIR objects"""
# Looks through the array of the codeable_concept for an entry matching the id and system.
# Returns the entry if found, or None if not found.
# def find_codable_concept(codeable_concept, id, system):
#    for entry in codeable_concept.coding:
#        if entry.system == system and entry.code == id:
#            return entry
#    return None

from collections.abc import Iterable
import json  # noqa: F401 pylint: disable=unused-import
from typing import Union

from fhir.resources.bundle import Bundle
from fhir.resources.bundle import BundleEntry, BundleEntryRequest
from fhir.resources.codeableconcept import CodeableConcept
from fhir.resources.coding import Coding
from fhir.resources.condition import Condition  # noqa: F401 pylint: disable=unused-import
from fhir.resources.element import Element
from fhir.resources.extension import Extension
from fhir.resources.identifier import Identifier
from fhir.resources.medicationstatement import MedicationStatement  # noqa: F401 pylint: disable=unused-import
from fhir.resources.meta import Meta

from text_analytics import insight_constants  # noqa: F401 pylint: disable=unused-import
from text_analytics.insight_constants import CLASSIFICATION_DERIVED_CODE
from text_analytics.insight_constants import CLASSIFICATION_DERIVED_SYSTEM
from text_analytics.insight_constants import INSIGHT_CATEGORY_URL


def find_codings(codeable_concept: CodeableConcept,
                 code_system_url: str,
                 code_id: str) -> list[Coding]:
    """Returns a list of coding elements that match the system url and id."""
    if codeable_concept.coding is None:
        return []

    return list(
        filter(lambda coding: coding.system == code_system_url and coding.code == code_id,
               codeable_concept.coding)
        )


def _get_extension(element: Element,
                   extension_url: str) -> Extension:
    """Returns the extension for the element with the provided url"""
    if element.extension:
        return next(filter(lambda extension: extension.url == extension_url,
                           element.extension),
                    None)
    return None


def get_derived_by_nlp_extension(element: Element):
    """Returns a derived by NLP extension if the element has one"""
    extension = _get_extension(element, extension_url=INSIGHT_CATEGORY_URL)
    try:
        if any(coding.system == CLASSIFICATION_DERIVED_SYSTEM and
               coding.code == CLASSIFICATION_DERIVED_CODE
               for coding in extension.valueCodeableConcept.coding):
            return extension
    except AttributeError:
        pass

    return None


def append_coding(codeable_concept: CodeableConcept,
                  system: str,
                  code: str,
                  display: str=None):
    """Append the coding to the codebale concept, if the coding does not exist

       This method will not append a new coding if the coding exists, even if the
       existing coding has an extension area indicating it is derived by NLP.

       Example:
        >>> concept = CodeableConcept.construct()
        >>> append_coding(concept,
        ...               'http://example_system',
        ...               'Code_12345',
        ...               'example display string')
        >>> print(concept.json(indent=2))
        {
          "coding": [
            {
              "code": "Code_12345",
              "display": "example display string",
              "system": "http://example_system"
            }
          ]
        }
    """
    if codeable_concept.coding is None:
        codeable_concept.coding = []

    existing_codings = find_codings(codeable_concept, system, code)
    if not existing_codings:
        new_coding = create_coding(system, code, display, derived_by_nlp=False)
        codeable_concept.coding.append(new_coding)


def append_derived_by_nlp_coding(codeable_concept: CodeableConcept,
                                 system: str,
                                 code: str,
                                 display: str=None):
    """Creates a coding and adds it to the codeable concept if the coding does not exist

       If the coding exists, but does not have the derived by NLP extension, a new coding
       is added.

       Example:
        >>> concept = CodeableConcept.construct()
        >>> append_derived_by_nlp_coding(concept,
        ...                             'http://example_system',
        ...                             'Code_12345',
        ...                             'example display string')
        >>> print(concept.json(indent=2))
        {
          "coding": [
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
              "code": "Code_12345",
              "display": "example display string",
              "system": "http://example_system"
            }
          ]
        }

        Second append doesn't append a new coding
        >>> append_derived_by_nlp_coding(concept,
        ...                             'http://example_system',
        ...                             'Code_12345',
        ...                             'example display string')
        >>> print(concept.json(indent=2))
        {
          "coding": [
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
              "code": "Code_12345",
              "display": "example display string",
              "system": "http://example_system"
            }
          ]
        }
    """
    if codeable_concept.coding is None:
        codeable_concept.coding = []

    existing_codings = find_codings(codeable_concept, system, code)
    if (existing_codings and any(get_derived_by_nlp_extension(coding)
                                 for coding in existing_codings)):
        # there is already a derived extension on at least one coding
        pass
    else:
        # coding exists, but no derived extension, or coding does not exist add new coding
        new_coding = create_coding(system, code, display, derived_by_nlp=True)
        codeable_concept.coding.append(new_coding)


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


def create_confidence_extension(name, value):
    """Creates a FHIR extension element for insight confidence

       Example:
        >>> print(create_confidence_extension('insight', 1.0).json(indent=2))
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


# TODO: Does a derived NLP extension need to reference the insight id in meta?
#       Seems like we need the linkage back to which insight / which NLP created the insight?
def create_derived_by_nlp_extension():
    """Creates an extension indicating the resource is derived from NLP

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


def create_insight_span_extension(begin, end, covered_text):
    """Creates an extension for the insight's span

       This extension is a list of begin-offset, end-offset, and covered-text
       extensions.

       Example:
        >>> extension = create_insight_span_extension(100,
        ...                                           123,
        ...                                           'this is my covered Text')
        >>> print(extension.json(indent=2))
        {
          "extension": [
            {
              "url": "http://ibm.com/fhir/cdm/StructureDefinition/covered-text",
              "valueString": "this is my covered Text"
            },
            {
              "url": "http://ibm.com/fhir/cdm/StructureDefinition/offset-begin",
              "valueInteger": 100
            },
            {
              "url": "http://ibm.com/fhir/cdm/StructureDefinition/offset-end",
              "valueInteger": 123
            }
          ],
          "url": "http://ibm.com/fhir/cdm/StructureDefinition/span"
        }
    """
    offset_begin_ext = Extension.construct()
    offset_begin_ext.url = insight_constants.INSIGHT_SPAN_OFFSET_BEGIN_URL
    offset_begin_ext.valueInteger = begin

    offset_end_ext = Extension.construct()
    offset_end_ext.url = insight_constants.INSIGHT_SPAN_OFFSET_END_URL
    offset_end_ext.valueInteger = end

    covered_text_ext = Extension.construct()
    covered_text_ext.url = insight_constants.INSIGHT_SPAN_COVERED_TEXT_URL
    covered_text_ext.valueString = covered_text

    insight_span_ext = Extension.construct()
    insight_span_ext.url = insight_constants.INSIGHT_SPAN_URL
    insight_span_ext.extension = [covered_text_ext]
    insight_span_ext.extension.append(offset_begin_ext)
    insight_span_ext.extension.append(offset_end_ext)

    return insight_span_ext


def create_insight_id_extension(insight_id_value, insight_system):
    """Creates an extension for an insight-id with a valueIdentifier

        Args:
            insight_id_value   - the value of the insight id
            insight_system     - urn for the system used to create the insight

        Returns: The insight extension

    Example:
    >>> ext = create_insight_id_extension("insight-1", "urn:id:COM.IBM.WH.PA.CDP.CDE/1.0.0")
    >>> print(ext.json(indent=2))
    {
      "url": "http://ibm.com/fhir/cdm/StructureDefinition/insight-id",
      "valueIdentifier": {
        "system": "urn:id:COM.IBM.WH.PA.CDP.CDE/1.0.0",
        "value": "insight-1"
      }
    }
    """
    insight_id_ext = Extension.construct()
    insight_id_ext.url = insight_constants.INSIGHT_ID_URL

    insight_id = Identifier.construct()
    insight_id.system = insight_system
    insight_id.value = insight_id_value

    insight_id_ext.valueIdentifier = insight_id
    return insight_id_ext


def append_derived_by_nlp_extension(resource):  # formerly create_derived_resource_extension
    """Append resource-level extension to resource, indicating resource was derived

       Does not check if the extension already exists

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


def create_insight_extension_in_meta(resource):
    """Adds an insight extension to the meta section of a resource

       The meta section of the resource is created if it does not exist.

       Args:
             resource - the resource to update with a new insight extension in meta

       Returns: The insight extension that was added

       Example:
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
        ... }''' ))

        >>> extension = create_insight_extension_in_meta(condition1)

        >>> print(extension.json(indent=2))
        {
          "url": "http://ibm.com/fhir/cdm/StructureDefinition/insight"
        }

        >>> print(condition1.json(indent=2))
        {
          "meta": {
            "extension": [
              {
                "url": "http://ibm.com/fhir/cdm/StructureDefinition/insight"
              }
            ]
          },
          "code": {
            "text": "Diabetes Mellitus, Insulin-Dependent"
          },
          "subject": {
            "reference": "Patient/7c33b82a-4efc-4082-9fe9-8122d6791552"
          },
          "resourceType": "Condition"
        }
    """
    if resource.meta is None:
        resource.meta = Meta.construct()

    insight_extension = Extension.construct()
    insight_extension.url = insight_constants.INSIGHT_URL

    if resource.meta.extension is None:
        resource.meta.extension = []

    resource.meta.extension.append(insight_extension)

    return insight_extension


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
