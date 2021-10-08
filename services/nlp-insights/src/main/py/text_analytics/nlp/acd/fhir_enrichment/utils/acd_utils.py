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


from typing import Generator
from typing import Iterable
from typing import List

from ibm_whcs_sdk.annotator_for_clinical_data import (
    annotator_for_clinical_data_v1 as acd,
)


def filter_attribute_values(
    attribute_values: List[acd.AttributeValueAnnotation], values: Iterable[str]
) -> Generator[acd.AttributeValueAnnotation, None, None]:
    """Generator to filter attributes by name of attribute

    Args:
        attribute_values - list of attribute value annotations from ACD
        values - allowed names for returned attributes
    """
    for attr in attribute_values:
        if attr.name in values:
            yield attr
