import logging
import os
import subprocess
from pathlib import Path
from osi_utilities import (
    ChannelSpecification,
    MessageType,
    TraceFileFormat,
    open_channel,
    open_channel_writer,
)

from osc_validation.tools.osctool import OSCTool
from osc_validation.utils.osi_channel_specification import (
    OSIChannelSpecValidator,
    with_name_suffix,
)


class GTGen_Simulator(OSCTool):
    """
    This class serves as a tool for interacting with the gtgen simulator via gtgen_cli.
    """

    def __init__(self, tool_path=None):
        super().__init__(self.resolve_tool_path(tool_path, "gtgen_cli"))

    def get_version(self) -> list[str]:
        cmd = [str(self.tool_path), "--version"]
        res = subprocess.run(cmd, capture_output=True, text=True, check=False)
        stdout = (res.stdout or "").strip()
        text_out = stdout if stdout else "unknown version"
        return [line.strip() for line in text_out.splitlines() if line.strip()]

    def run(
        self,
        osc_path: Path,
        odr_path: Path,
        osi_output_spec: ChannelSpecification,
        log_path: Path = None,
        rate=None,
    ) -> ChannelSpecification:
        """
        Executes the gtgen_cli tool with the specified input files and parameters.

        Args:
            osc_path (Path): Path to the OpenSCENARIO (.xosc) file.
            odr_path (Path): Path to the OpenDRIVE (.xodr) file.
            osi_output_spec (ChannelSpecification): Requested OSI channel specification of the output trace.
                Allowed message type is "SensorView"; If none given, it will output a SensorView trace.
            log_path (Path, optional): Path to the directory where logs will be stored. If None, logs will not be saved but printed to stdout.
            rate (float, optional): Step size in seconds.
        Returns:
            ChannelSpecification: The OSI channel specification for the output trace.
        Raises:
            InvalidSpecificationError: If the requested OSI output specification is invalid or unsupported.
            FileNotFoundError: If the GTGen tool is not found at the specified path.
            RuntimeError: If the trace could not be generated.
        """
        # Check if the requested output specification is supported
        requested_spec_validator = OSIChannelSpecValidator(
            allowed_message_types=[MessageType.SENSOR_VIEW]
        )
        requested_spec_validator(osi_output_spec)

        osi_gtgen_sv_spec = (
            with_name_suffix(osi_output_spec, "_gtgen")
            .with_trace_file_format(TraceFileFormat.SINGLE_CHANNEL)
            .with_message_type(MessageType.SENSOR_VIEW)
        )

        cmd = [
            self.tool_path,
            "-s",
            osc_path,
            "--gtgen-data",
            "./GTGEN_DATA",
            "--output-trace",
            osi_gtgen_sv_spec.path,
        ]

        if rate is not None:
            cmd.extend(["--step-size-ms", str(rate * 1000)])

        if log_path is not None:
            cmd.extend(["--log-file-dir", str(log_path)])

        cmd_str = " ".join(map(str, cmd))
        logging.info(f"Running gtgen_cli with command: '{cmd_str}'")
        os.system(cmd_str)
        if not osi_gtgen_sv_spec.exists():
            raise RuntimeError(
                f"GTGen trace could not be generated. Check the tool's logs for more details."
            )
        logging.info(f"GTGen temp output: {osi_gtgen_sv_spec}")

        # Adapt output trace file format according to the requested specification
        output_spec = None
        with (
            open_channel_writer(osi_output_spec) as writer,
            open_channel(osi_gtgen_sv_spec) as reader,
        ):
            for message in reader:
                writer.write_message(message)
        output_spec = writer.get_channel_specification()

        logging.info(f"Output trace specification: {output_spec}")

        return output_spec
