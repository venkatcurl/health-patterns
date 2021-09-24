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

# Types of data to process for enrichment
ALLERGEN = 'ALLERGEN'
CONDITION = 'CONDITION'
MANIFESTATION = 'MANIFESTATION'
VACCINE = 'VACCINE'

# List of NLP annotations to use by FHIR resource type
annotation_type_allergy = ['CDP-Allergy']
ANNOTATION_TYPE_CONDITION = ['CDP-Condition']
annotation_type_immunization = ['CDP-Immunization']
ANNOTATION_TYPE_MEDICATION = ['CDP-Medication']
