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


# Given an ACD attribute, and a set of ACD annotations, finds the annotation associated
# with the attribute.
# The "associated" annotation is the annotation with the uid indicated in the attribute
# this will be the "source" for the attribute (eg the Concept used to create the attribute).
def get_source_for_attribute(attr, concepts):
    concept = attr.concept
    uid = concept.uid
    for c in concepts:
        if c.uid == uid:
            return c
    return None
