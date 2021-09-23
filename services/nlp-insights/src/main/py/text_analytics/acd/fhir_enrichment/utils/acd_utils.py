# *******************************************************************************
# IBM Confidential                                                            *
#                                                                             *
# OCO Source Materials                                                        *
#                                                                             *
# (C) Copyright IBM Corp. 2021                                                *
#                                                                             *
# The source code for this program is not published or otherwise              *
# divested of its trade secrets, irrespective of what has been                *
# deposited with the U.S. Copyright Office.                                   *
# ******************************************************************************/


from typing import Iterable

from ibm_whcs_sdk.annotator_for_clinical_data import (
    annotator_for_clinical_data_v1 as acd_v1,
)


def get_annotation_for_attribute(
    attr: acd_v1.AttributeValueAnnotation, acd_annotations: Iterable[acd_v1.MedicationAnnotation]
) -> acd_v1.MedicationAnnotation:
    """Finds the annotation associated with the ACD attribute.

    The "associated" annotation is the one with the uid indicated by the attribute.
    This will be the "source" for the attribute (eg the annotation used to create the attribute).

     Args:
        attr - the ACD attribute value
        acd_annotations - the list of acd concepts to search

     Returns:
        The concept that was used to create the attribute.
    """
    concept = attr.concept
    uid = concept.uid
    for acd_annotation in acd_annotations:
        if acd_annotation.uid == uid:
            return acd_annotations
    return None



