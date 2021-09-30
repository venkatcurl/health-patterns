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


import json  # noqa: F401 pylint: disable=unused-import
from typing import List
from typing import NamedTuple
from typing import Optional
from typing import Tuple

from fhir.resources.bundle import Bundle
from fhir.resources.bundle import BundleEntry, BundleEntryRequest
from fhir.resources.codeableconcept import CodeableConcept
from fhir.resources.coding import Coding
from fhir.resources.condition import (  # noqa: F401 pylint: disable=unused-import
    Condition,
)
from fhir.resources.diagnosticreport import (  # noqa: F401 pylint: disable=unused-import
    DiagnosticReport,
)
from fhir.resources.documentreference import (  # noqa: F401 pylint: disable=unused-import
    DocumentReference,
)
from fhir.resources.element import Element
from fhir.resources.extension import Extension
from fhir.resources.identifier import Identifier
from fhir.resources.medicationstatement import (  # noqa: F401 pylint: disable=unused-import
    MedicationStatement,
)
from fhir.resources.meta import Meta
from fhir.resources.reference import Reference
from fhir.resources.resource import Resource

from text_analytics import insight_constants  # noqa: F401 pylint: disable=unused-import
from text_analytics.insight_constants import CLASSIFICATION_DERIVED_CODE
from text_analytics.insight_constants import CLASSIFICATION_DERIVED_SYSTEM
from text_analytics.insight_constants import INSIGHT_CATEGORY_URL
from text_analytics.insight_source import UnstructuredSource
from text_analytics.span import Span


def find_codings(
    codeable_concept: CodeableConcept, system: str, code: str
) -> List[Coding]:
    """Returns a list of coding elements that match the system url and id."""
    if codeable_concept.coding is None:
        return []

    return list(
        filter(lambda c: c.system == system and c.code == code, codeable_concept.coding)
    )


def _get_extension(element: Element, extension_url: str) -> Optional[Extension]:
    """Returns the extension for the element with the provided url"""
    if element.extension:
        return next(
            filter(lambda extension: extension.url == extension_url, element.extension),
            None,
        )
    return None


def get_derived_by_nlp_extension(element: Element) -> Optional[Extension]:
    """Returns a derived by NLP extension if the element has one"""
    extension = _get_extension(element, extension_url=INSIGHT_CATEGORY_URL)
    if extension.valueCodeableConcept.coding and any(
        coding
        and coding.system
        and coding.code
        and coding.system == CLASSIFICATION_DERIVED_SYSTEM
        and coding.code == CLASSIFICATION_DERIVED_CODE
        for coding in extension.valueCodeableConcept.coding
    ):
        return extension

    return None


def append_coding(
    codeable_concept: CodeableConcept, system: str, code: str, display: str = None
) -> None:
    """Append the coding to the codebale concept, if the coding does not exist

    This method will not append a new coding if the coding exists, even if the
    existing coding has an extension area indicating it is derived by NLP.

    A derived by NLP extension will NOT be added to the new coding

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


def append_derived_by_nlp_coding(
    codeable_concept: CodeableConcept, system: str, code: str, display: str = None
) -> None:
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
    if existing_codings and any(
        get_derived_by_nlp_extension(coding) for coding in existing_codings
    ):
        # there is already a derived extension on at least one coding
        pass
    else:
        # coding exists, but no derived extension, or coding does not exist add
        # new coding
        new_coding = create_coding(system, code, display, derived_by_nlp=True)
        codeable_concept.coding.append(new_coding)


# FIXME: former create_coding_system_entry_with_extension
def create_coding(
    system: str, code: str, display: str = None, derived_by_nlp: bool = False
) -> Element:
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


def create_confidence_extension(name: str, value: str) -> Extension:
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
          "valueDecimal": 1.0
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
    confidence_score.valueDecimal = value

    confidence.extension = [confidence_name]
    confidence.extension.append(confidence_score)
    return confidence


def create_derived_by_nlp_extension() -> Extension:
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
    classification_coding = create_coding(
        insight_constants.CLASSIFICATION_DERIVED_SYSTEM,
        insight_constants.CLASSIFICATION_DERIVED_CODE,
        insight_constants.CLASSIFICATION_DERIVED_DISPLAY,
    )
    classification_value = CodeableConcept.construct()
    classification_value.coding = [classification_coding]
    classification_value.text = insight_constants.CLASSIFICATION_DERIVED_DISPLAY
    classification_ext.valueCodeableConcept = classification_value
    return classification_ext


def create_derived_from_concept_insight_detail_extension(
    reference_path_ext: Extension,
    nlp_extensions: Optional[List[Extension]] = None,
) -> Extension:
    """Creates an insight detail extension that includes NLP extensions

    This is used to indicate that a resource has been enhanced with
    additional codings/insights. By running NLP over existing concepts
    in the resource.

    Args:
        nlp_extensions - optional additional insight data from NLP
                        (such as the raw data structure returned from NLP)
    Returns:
        the extension

    Example:
    >>> nlp_extensions = [
    ...                   Extension.construct(
    ...                    url='http://ibm.com/fhir/cdm/StructureDefinition/evaluated-output')
    ...                  ]
    >>> reference_path_ext = create_reference_path_extension('AllergyIntolerance.code')
    >>> ext = create_derived_from_concept_insight_detail_extension(reference_path_ext, nlp_extensions)
    >>> print(ext.json(indent=2))
    {
      "extension": [
        {
          "url": "http://ibm.com/fhir/cdm/StructureDefinition/evaluated-output"
        },
        {
          "url": "http://ibm.com/fhir/cdm/StructureDefinition/reference-path",
          "valueString": "AllergyIntolerance.code"
        }
      ],
      "url": "http://ibm.com/fhir/cdm/StructureDefinition/insight-detail"
    }
    """
    insight_detail = Extension.construct()
    insight_detail.url = insight_constants.INSIGHT_DETAIL_URL
    if insight_detail.extension is None:
        insight_detail.extension = []

    if nlp_extensions:
        insight_detail.extension.extend(nlp_extensions)

    if reference_path_ext:
        insight_detail.extension.append(reference_path_ext)

    return insight_detail


def create_derived_from_unstructured_insight_detail_extension(
    source: UnstructuredSource,
    confidences: Optional[List[Extension]] = None,
    nlp_extensions: Optional[List[Extension]] = None,
) -> Extension:
    """Creates an insight detail extension for a derived resource

    The derived resource is expected to have been derived based on unstructured data in
    the source resource.

    Args:
        source - the resource containing the unstructured data used to derive the insight resource
        confidences - optional confidence extensions associated with the insight
        nlp_extensions - optional additional insight data from NLP
                        (such as the raw data structure returned from NLP)

    Example:
    >>> visit_code = CodeableConcept.construct(text='Mental status Narrative')
    >>> report = DiagnosticReport.construct(id='12345',
    ...                                     code=visit_code,
    ...                                     text='crazy')
    >>> source = UnstructuredSource(resource=report,
    ...                             text_span=Span(begin=0,end=5,covered_text='crazy'))
    >>> confidences = [ create_confidence_extension('Suspected Score', .99) ]
    >>> nlp_extensions = [
    ...                   Extension.construct(
    ...                    url='http://ibm.com/fhir/cdm/StructureDefinition/evaluated-output')
    ...                  ]
    >>> extension = create_derived_from_unstructured_insight_detail_extension(source,
    ...                                                                       confidences,
    ...                                                                       nlp_extensions)
    >>> print(extension.json(indent=2))
    {
      "extension": [
        {
          "url": "http://ibm.com/fhir/cdm/StructureDefinition/evaluated-output"
        },
        {
          "url": "http://ibm.com/fhir/cdm/StructureDefinition/reference",
          "valueReference": {
            "reference": "DiagnosticReport/12345"
          }
        },
        {
          "extension": [
            {
              "extension": [
                {
                  "url": "http://ibm.com/fhir/cdm/StructureDefinition/covered-text",
                  "valueString": "crazy"
                },
                {
                  "url": "http://ibm.com/fhir/cdm/StructureDefinition/offset-begin",
                  "valueInteger": 0
                },
                {
                  "url": "http://ibm.com/fhir/cdm/StructureDefinition/offset-end",
                  "valueInteger": 5
                },
                {
                  "extension": [
                    {
                      "url": "http://ibm.com/fhir/cdm/StructureDefinition/description",
                      "valueString": "Suspected Score"
                    },
                    {
                      "url": "http://ibm.com/fhir/cdm/StructureDefinition/score",
                      "valueDecimal": 0.99
                    }
                  ],
                  "url": "http://ibm.com/fhir/cdm/StructureDefinition/insight-confidence"
                }
              ],
              "url": "http://ibm.com/fhir/cdm/StructureDefinition/span"
            }
          ],
          "url": "http://ibm.com/fhir/cdm/StructureDefinition/insight-result"
        }
      ],
      "url": "http://ibm.com/fhir/cdm/StructureDefinition/insight-detail"
    }
    """
    insight_span_ext = create_insight_span_extension(source.text_span)

    if confidences:
        if insight_span_ext.extension is None:
            insight_span_ext.extension = []
        insight_span_ext.extension.extend(confidences)
    else:
        pass

    # Unstructured results extension
    insight_results = Extension.construct()
    insight_results.url = insight_constants.INSIGHT_RESULT_URL
    insight_results.extension = [insight_span_ext]

    # Create reference to unstructured report
    report_reference_ext = create_reference_to_resource_extension(source.resource)

    insight_detail = Extension.construct()
    insight_detail.url = insight_constants.INSIGHT_DETAIL_URL
    insight_detail.extension = nlp_extensions.copy() if nlp_extensions else []
    insight_detail.extension.extend([report_reference_ext, insight_results])

    return insight_detail


def create_insight_span_extension(span: Span) -> Extension:
    """Creates an extension for the insight's span

    This extension is a list of begin-offset, end-offset, and covered-text
    extensions.

    Example:
     >>> extension = create_insight_span_extension(
     ...                 Span(begin=100,
     ...                      end=123,
     ...                      covered_text='this is my covered Text')
     ...             )
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
    offset_begin_ext.valueInteger = span.begin

    offset_end_ext = Extension.construct()
    offset_end_ext.url = insight_constants.INSIGHT_SPAN_OFFSET_END_URL
    offset_end_ext.valueInteger = span.end

    covered_text_ext = Extension.construct()
    covered_text_ext.url = insight_constants.INSIGHT_SPAN_COVERED_TEXT_URL
    covered_text_ext.valueString = span.covered_text

    insight_span_ext = Extension.construct()
    insight_span_ext.url = insight_constants.INSIGHT_SPAN_URL
    insight_span_ext.extension = [covered_text_ext]
    insight_span_ext.extension.append(offset_begin_ext)
    insight_span_ext.extension.append(offset_end_ext)

    return insight_span_ext


def create_insight_id_extension(
    insight_id_value: str, insight_system: str
) -> Extension:
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


# formerly create_derived_resource_extension
def append_derived_by_nlp_extension(resource: Resource) -> None:
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


def add_insight_to_meta(
    resource: Resource, insight_id: Extension, insight_detail: Extension
) -> None:
    """Updates a resource with an insight extension in the meta

    The meta section of the resource is created if it does not exist.

    Args:
          resource - the resource to update with a new insight extension in meta
          insight_id - a resource id extension
                       see: create_insight_id_extension
          insight_detail - an insight details extension

    Example:
    Create Example Resource:
    >>> visit_code = CodeableConcept.construct(text='Mental status Narrative')
    >>> report = DiagnosticReport.construct(id='12345',
    ...                                     code=visit_code,
    ...                                     text='crazy',
    ...                                     status='final')

    Create Insight ID extension:
    >>> insight_id = create_insight_id_extension('insight-1', 'urn:id:COM.IBM.WH.PA.CDP.CDE/1.0.0')

    Create Insight detail Extension:
    >>> source = UnstructuredSource(resource=report,
    ...                             text_span=Span(begin=0,end=5,covered_text='crazy'))
    >>> confidences = [ create_confidence_extension('Suspected Score', .99) ]
    >>> nlp_extensions = [
    ...                   Extension.construct(
    ...                    url='http://ibm.com/fhir/cdm/StructureDefinition/evaluated-output')
    ...                  ]
    >>> insight_detail = create_derived_from_unstructured_insight_detail_extension(source,
    ...                                                                            confidences,
    ...                                                                            nlp_extensions)

    Add Insight to meta:
    >>> add_insight_to_meta(report, insight_id, insight_detail)
    >>> print(report.json(indent=2))
    {
      "id": "12345",
      "meta": {
        "extension": [
          {
            "extension": [
              {
                "url": "http://ibm.com/fhir/cdm/StructureDefinition/insight-id",
                "valueIdentifier": {
                  "system": "urn:id:COM.IBM.WH.PA.CDP.CDE/1.0.0",
                  "value": "insight-1"
                }
              },
              {
                "extension": [
                  {
                    "url": "http://ibm.com/fhir/cdm/StructureDefinition/evaluated-output"
                  },
                  {
                    "url": "http://ibm.com/fhir/cdm/StructureDefinition/reference",
                    "valueReference": {
                      "reference": "DiagnosticReport/12345"
                    }
                  },
                  {
                    "extension": [
                      {
                        "extension": [
                          {
                            "url": "http://ibm.com/fhir/cdm/StructureDefinition/covered-text",
                            "valueString": "crazy"
                          },
                          {
                            "url": "http://ibm.com/fhir/cdm/StructureDefinition/offset-begin",
                            "valueInteger": 0
                          },
                          {
                            "url": "http://ibm.com/fhir/cdm/StructureDefinition/offset-end",
                            "valueInteger": 5
                          },
                          {
                            "extension": [
                              {
                                "url": "http://ibm.com/fhir/cdm/StructureDefinition/description",
                                "valueString": "Suspected Score"
                              },
                              {
                                "url": "http://ibm.com/fhir/cdm/StructureDefinition/score",
                                "valueDecimal": 0.99
                              }
                            ],
                            "url": "http://ibm.com/fhir/cdm/StructureDefinition/insight-confidence"
                          }
                        ],
                        "url": "http://ibm.com/fhir/cdm/StructureDefinition/span"
                      }
                    ],
                    "url": "http://ibm.com/fhir/cdm/StructureDefinition/insight-result"
                  }
                ],
                "url": "http://ibm.com/fhir/cdm/StructureDefinition/insight-detail"
              }
            ],
            "url": "http://ibm.com/fhir/cdm/StructureDefinition/insight"
          }
        ]
      },
      "text": "crazy",
      "code": {
        "text": "Mental status Narrative"
      },
      "status": "final",
      "resourceType": "DiagnosticReport"
    }
    """

    insight_extension = Extension.construct()
    insight_extension.url = insight_constants.INSIGHT_URL
    insight_extension.extension = [insight_id, insight_detail]

    if resource.meta is None:
        resource.meta = Meta.construct()

    if resource.meta.extension is None:
        resource.meta.extension = []

    resource.meta.extension.append(insight_extension)


class BundleEntryDfn(NamedTuple):
    """Entry used by create_transaction_bundle to create a bundle"""

    resource: Resource
    method: str
    url: str


def create_transaction_bundle(resource_action_list: List[BundleEntryDfn]) -> Bundle:
    """Creates a bundle from a list of bundle resources

    Args:
        resource_action_list - list of bundle resources

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
    >>> bundle = create_transaction_bundle([BundleEntryDfn(condition1, 'POST', 'http://url1'),
    ...                                     BundleEntryDfn(condition2, 'POST', 'http://url2')])
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

    for res_act in resource_action_list:
        bundle_entry = BundleEntry.construct()
        bundle_entry.resource = res_act.resource
        request = BundleEntryRequest.construct(method=res_act.method, url=res_act.url)
        bundle_entry.request = request
        bundle.entry.append(bundle_entry)

    return bundle


def create_reference_path_extension(path: str) -> Extension:
    """Creates an extension for an insight's reference path

    This is the location within the FHIR resource that
    caused the insight to be created.

    Example:
    >>> ext = create_reference_path_extension('AllergyIntolerance.code')
    >>> print(ext.json(indent=2))
    {
      "url": "http://ibm.com/fhir/cdm/StructureDefinition/reference-path",
      "valueString": "AllergyIntolerance.code"
    }
    """
    reference_ext = Extension.construct()
    reference_ext.url = insight_constants.INSIGHT_REFERENCE_PATH_URL
    reference_ext.valueString = path
    return reference_ext


def create_reference_to_resource_extension(resource: Resource) -> Extension:
    """Creates an extension to reference the resource

    This is used to explain where the passed resource came from.

    Args:
        resource - FHIR resource to reference

    Returns:
        the "based-on" extension

    Example:
    >>> visit_code = CodeableConcept.construct(text='Mental status Narrative')
    >>> d = DiagnosticReport.construct(id='12345',
    ...                                code=visit_code,
    ...                                text='crazy',
    ...                                status='final')
    >>> ext = create_reference_to_resource_extension(d)
    >>> print(ext.json(indent=2))
    {
      "url": "http://ibm.com/fhir/cdm/StructureDefinition/reference",
      "valueReference": {
        "reference": "DiagnosticReport/12345"
      }
    }
    """
    reference_id = resource.id if resource.id else "_unknown_"
    reference = Reference.construct()
    reference.reference = resource.resource_type + "/" + reference_id

    based_on_extension = Extension.construct()
    based_on_extension.url = insight_constants.INSIGHT_BASED_ON_URL
    based_on_extension.valueReference = reference
    return based_on_extension
