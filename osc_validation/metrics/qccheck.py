import logging
from pathlib import Path

from qc_baselib import Configuration

from qc_ositrace import constants
from qc_ositrace.main import run_checker_bundle
from qc_ositrace.checks.osirules import osirules_constants
from qc_ositrace.checks.deserialization import deserialization_constants

from osc_validation.utils.osi_channel_specification import OSIChannelSpecification, TraceFileFormat
from osc_validation.utils.osi_reader import OSIChannelReader
from osc_validation.utils.osi_writer import OSIChannelWriter


class TraceChecker:
    """
    Base class for checking OSI traces.
    """
    def __init__(self, osi_version: str):
        self.osi_version = osi_version

    def check(self, channel_spec: OSIChannelSpecification):
        return NotImplementedError("Subclasses should implement this method.")


class QCOSITraceChecker(TraceChecker):
    """
    Class to perform OSI trace checker bundle using the QC framework.
    
    Args:
        osi_version (str, optional): OSI version ruleset to be checked against. Defaults to None.
        ruleset (Path, optional): Path to the custom ruleset for OSITrace quality checks (osiRulesFile). If None, only the OSI version ruleset is checked.
    """
    def __init__(self, osi_version: str = None, ruleset: Path = None):
        super().__init__(osi_version)
        self.checker_bundle_name = constants.BUNDLE_NAME
        self.ruleset = ruleset

    def check(self, channel_spec: OSIChannelSpecification, result_file: Path = None, output_config: Path = None) -> bool:
        """
        Executes the configured OSI trace checker bundle on the provided OSI trace file.
        
        Args:
            trace (OSIChannelSpecification): Path to the OSI trace file to be checked.
            result_file (Path, optional): Path to the xqar output file where results will be written. If None, results will not be written to a file.
            output_config (Path, optional): Path to the output configuration xml file where the configuration will be written. If None, configuration will not be written to a file.
        
        Returns:
            bool: True if all checkers completed without issues, False otherwise.
        """

        # rewrite the trace to a single-channel file if it is not already in that format
        if channel_spec.trace_file_format == TraceFileFormat.SINGLE_CHANNEL:
            single_channel_trace_spec = channel_spec
        else:
            single_channel_trace_spec = channel_spec.with_trace_file_format(TraceFileFormat.SINGLE_CHANNEL).with_name_suffix("_qc")
            with OSIChannelReader.from_osi_channel_specification(channel_spec) as reader:
                with OSIChannelWriter.from_osi_channel_specification(single_channel_trace_spec) as writer:
                    for message in reader:
                        writer.write(message)

        config = Configuration()
        config.set_config_param("InputFile", str(single_channel_trace_spec.path))
        config.set_config_param("osiType", "SensorView")
        if self.osi_version:
            config.set_config_param("osiVersion", self.osi_version)
        if self.ruleset is not None:
            config.set_config_param("osiRulesFile", str(self.ruleset))
        config.register_checker_bundle(self.checker_bundle_name)
        if result_file:
            config.set_checker_bundle_param(
                checker_bundle_name=self.checker_bundle_name,
                name="resultFile",
                value=str(result_file),
            )

        result = run_checker_bundle(config)

        if config.get_checker_bundle_param(
            checker_bundle_name=constants.BUNDLE_NAME, param_name="resultFile"
        ):
            logging.info(f"Writing results to {result_file}")

            result.write_to_file(
                config.get_checker_bundle_param(
                    checker_bundle_name=constants.BUNDLE_NAME, param_name="resultFile"
                )
            )
        else:
            logging.info("No result file specified, results will not be written to file")

        if output_config:
            logging.info(f"Writing configuration to file: {output_config}")
            config.write_to_file(output_config)

        return result.all_checkers_completed_without_issue([osirules_constants.CHECKER_ID,
                                                            deserialization_constants.CHECKER_ID])
