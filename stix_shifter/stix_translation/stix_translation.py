import importlib
from stix_shifter.stix_translation.src.patterns.parser import generate_query
from stix2patterns.validator import run_validator
from stix_shifter.stix_translation.src.stix_pattern_parser import parse_stix
import re
import json
from ..utils.error_response import ErrorResponder


TRANSLATION_MODULES = ['qradar', 'dummy', 'car', 'cim', 'splunk', 'elastic', 'bigfix', 'csa', 'csa:at', 'csa:nf', 'aws_security_hub', 'carbonblack']
RESULTS = 'results'
QUERY = 'query'


class StixValidationException(Exception):
    pass

class TranslationResultException(Exception):
    def __str__(self):
        return "Error when converting results to STIX"


class StixTranslation:
    """
    StixShifter class - implements translations of stix data
    """

    def __init__(self):
        self.args = []

    def translate(self, module, translate_type, data_source, data, options={}):
        """
        Translated queries to a specified format
        :param module: What module to use
        :type module: one of TRANSLATION_MODULES 'qradar', 'dummy'
        :param translate_type: translation of a query or result set must be either 'results' or 'query'
        :type translate_type: str
        :param data: the data to translate
        :type data: str
        :param options: translation options { stix_validator: bool }
        :type options: dict
        :return: translated results
        :rtype: str
        """
        dialect = None
        mod_dia = module.split(':', 1)
        module = mod_dia[0]
        if len(mod_dia) > 1:
            dialect = mod_dia[1]

        if module not in TRANSLATION_MODULES:
            raise NotImplementedError

        translator_module = importlib.import_module(
            "stix_shifter.stix_translation.src.modules." + module + "." + module + "_translator")

        if dialect is not None:
            interface = translator_module.Translator(dialect=dialect)
        else:
            interface = translator_module.Translator()

        try:
            if translate_type == QUERY:
                errors = []
                # Temporarily skip validation on patterns with START STOP qualifiers: validator doesn't yet support timestamp format
                start_stop_pattern = "START\s?t'\d{4}(-\d{2}){2}T\d{2}(:\d{2}){2}(\.\d+)?Z'\sSTOP"
                pattern_match = re.search(start_stop_pattern, data)
                if (not pattern_match):
                    errors = run_validator(data)
                if (errors != []):
                    raise StixValidationException(
                        "The STIX pattern has the following errors: {}".format(errors))
                else:
                    # Translating STIX pattern to antlr query object
                    query_object = generate_query(data)
                    # Converting query object to datasource query
                    parsed_stix = parse_stix(query_object)
                    # Todo: pass in the query_object instead of the data so we can remove multiple generate_query calls.
                    # Converting STIX pattern to datasource query
                    queries = interface.transform_query(data, options)
                    return {'queries': queries, 'parsed_stix': parsed_stix}
            elif translate_type == RESULTS:
                # Converting data from the datasource to STIX objects
                try:
                    return interface.translate_results(data_source, data, options)
                except Exception:
                    raise TranslationResultException()
            else:
                raise NotImplementedError('wrong parameter: ' + translate_type)
        except Exception as ex:
            print('caught exception: ' + str(ex) + " " + str(type(ex)))
            response = dict()
            ErrorResponder.fill_error(response, message_struct={'exception': ex})
            return response
