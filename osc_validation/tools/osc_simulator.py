"""Tool wrapper for PMSFIT/osc-simulator."""

import logging
import subprocess
import sys
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


class OscSimulator(OSCTool):
    """Tool wrapper for the osc-simulator OSC engine.

    osc-simulator takes a ``.xosc`` file and emits ASAM OSI SensorView trace
    files via its CLI entry point (``osc-simulator``).

    It has no road-network model, so ``odr_path`` is accepted for interface
    compatibility but not forwarded to the underlying process.
    """

    def __init__(self, tool_path=None):
        super().__init__(self.resolve_tool_path(tool_path, "osc-simulator"))

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
        rate: float = 0.05,
    ) -> ChannelSpecification:
        """Execute osc-simulator and return the resulting OSI channel specification.

        Args:
            osc_path (Path): Path to the OpenSCENARIO (.xosc) file.
            odr_path (Path): Path to the OpenDRIVE (.xodr) file.  Accepted for
                interface compatibility but not forwarded to osc-simulator, which
                has no road-network model.
            osi_output_spec (ChannelSpecification): Requested OSI channel
                specification of the output trace.  Allowed message type is
                ``SensorView``.
            log_path (Path, optional): Directory where the osc-simulator console
                log will be stored.  If ``None``, output is forwarded to stdout/
                stderr and not saved.
            rate (float, optional): Simulation time step in seconds.
                Defaults to 0.05.

        Returns:
            ChannelSpecification: Specification of the output OSI channel.

        Raises:
            InvalidSpecificationError: If the requested OSI output specification
                is invalid or unsupported.
            FileNotFoundError: If osc-simulator is not found at the specified
                path or on PATH.
            RuntimeError: If the trace could not be generated.
        """
        # Validate the requested output specification
        requested_spec_validator = OSIChannelSpecValidator(
            allowed_message_types=[MessageType.SENSOR_VIEW]
        )
        requested_spec_validator(osi_output_spec)

        # osc-simulator writes <stem>_channel0.osi into the output directory.
        # Use a unique suffix so that parallel test runs do not collide.
        osi_osc_sv_spec = (
            with_name_suffix(osi_output_spec, "_osc_simulator")
            .with_trace_file_format(TraceFileFormat.SINGLE_CHANNEL)
            .with_message_type(MessageType.SENSOR_VIEW)
        )

        # osc-simulator expects the output directory to exist; it determines
        # the filename from the scenario stem, so we derive the expected path.
        output_dir = osi_osc_sv_spec.path.parent
        output_dir.mkdir(parents=True, exist_ok=True)
        expected_output = output_dir / f"{Path(osc_path).stem}_channel0.osi"

        cmd = [
            str(self.tool_path),
            str(osc_path),
            "-o",
            str(output_dir),
            "--step-size",
            str(rate),
            "--reported-osi-version",
            "3.7.0"
        ]

        cmd_str = " ".join(map(str, cmd))
        logging.info("Running osc-simulator with command: '%s'", cmd_str)

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            errors="replace",
            check=False,
        )

        if result.stdout:
            print(result.stdout, end="")
        if result.stderr:
            print(result.stderr, end="", file=sys.stderr)

        if log_path is not None:
            log_dir = Path(log_path)
            log_dir.mkdir(parents=True, exist_ok=True)
            console_log = log_dir / "osc_simulator.log"
            console_log.write_text(
                f"$ {cmd_str}\n"
                f"exit code: {result.returncode}\n\n"
                f"--- stdout ---\n{result.stdout or ''}\n"
                f"--- stderr ---\n{result.stderr or ''}\n",
                encoding="utf-8",
            )
            logging.info("osc-simulator console output: %s", console_log)

        if not expected_output.exists():
            raise RuntimeError(
                "osc-simulator trace could not be generated. "
                "Check the tool's logs for more details."
            )

        logging.info("osc-simulator temp output: %s", expected_output)

        # Convert / copy to the requested output specification
        with (
            open_channel_writer(osi_output_spec) as writer,
            open_channel(
                ChannelSpecification(
                    path=expected_output,
                    message_type=MessageType.SENSOR_VIEW,
                )
            ) as reader,
        ):
            for message in reader:
                writer.write_message(message)

        output_spec = writer.get_channel_specification()
        logging.info("Output trace specification: %s", output_spec)
        return output_spec

