"""Typer CLI entry point for Cloud Readers."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import typer
import numpy as np
from rich.console import Console
from rich.table import Table

from . import extraction, ingestion, kinematics, serialization, simulation

console = Console()
app = typer.Typer(help="Cloud Readers: resurrect biomechanics from static art")


def configure_logger(verbose: bool) -> logging.Logger:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    return logging.getLogger("cloud-readers")


@app.command()
def extract(
    source: Path = typer.Option(..., exists=True, readable=True, path_type=Path, help="Source artwork to ingest."),
    device: str = typer.Option("generic", help="Device profile label."),
    style: str = typer.Option("neutral", help="Artistic intent for metadata tagging."),
    out: Path = typer.Option(Path("./artifacts/extraction"), path_type=Path, help="Directory to store intermediate outputs."),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable debug logging."),
):
    """Run ingestion, extraction, and kinematics reconstruction."""

    logger = configure_logger(verbose)
    ingest_config = ingestion.IngestionConfig(source=source, device=device, style=style)
    ingested = ingestion.ingest(ingest_config, logger)
    extracted = extraction.extract_features(ingested, logger)
    kine = kinematics.reconstruct_power_law(extracted, logger)

    serialization.export_intermediate(extracted, out, logger)
    serialization.export_kinematics(kine, out, logger)

    table = Table(title="Extraction Summary")
    table.add_column("Key", style="cyan")
    table.add_column("Value", style="magenta")
    table.add_row("Points", str(len(kine.profile.points)))
    table.add_row("Mean velocity", f"{kine.metadata['mean_velocity']:.4f}")
    table.add_row("Edge density", f"{extracted.metadata['edge_density']:.4f}")
    console.print(table)


@app.command()
def simulate(
    input_dir: Path = typer.Option(..., exists=True, file_okay=False, path_type=Path, help="Directory containing kinematics.json."),
    physics_engine: str = typer.Option("internal", help="Physics backend name."),
    sample_rate_hz: float = typer.Option(200.0, help="Sampling rate for synthetic IMU channels."),
    noise_std: float = typer.Option(0.01, help="Standard deviation for Gaussian sensor noise."),
    gravity: str = typer.Option("0,0,-1", help="Gravity direction vector as comma-separated x,y,z."),
    out: Path = typer.Option(Path("./artifacts/simulation"), path_type=Path, help="Directory to store simulated data."),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable debug logging."),
):
    """Generate IMU-like channels from extracted kinematics."""

    def _parse_gravity(raw: str) -> tuple[float, float, float]:
        parts = [p.strip() for p in raw.split(",") if p.strip()]
        if len(parts) != 3:
            raise typer.BadParameter("Gravity vector must have three comma-separated components")
        try:
            return float(parts[0]), float(parts[1]), float(parts[2])
        except ValueError as exc:
            raise typer.BadParameter("Gravity vector components must be numeric") from exc

    logger = configure_logger(verbose)
    kinematics_path = input_dir / "kinematics.json"
    if not kinematics_path.exists():
        raise FileNotFoundError(f"Missing kinematics.json in {input_dir}")

    kine = serialization.load_kinematics(kinematics_path, logger)
    sim_config = simulation.SimulationConfig(
        sample_rate_hz=sample_rate_hz,
        noise_std=noise_std,
        gravity_direction=_parse_gravity(gravity),
    )
    simulated = simulation.simulate_motion(
        kine,
        physics_engine=physics_engine,
        logger=logger,
        config=sim_config,
    )
    serialization.export_simulation(simulated, out, logger)

    console.print(f"Simulated data written to {out}")


@app.command()
def export(
    extraction_dir: Path = typer.Option(..., exists=True, file_okay=False, path_type=Path, help="Folder with extraction artifacts."),
    simulation_dir: Path = typer.Option(..., exists=True, file_okay=False, path_type=Path, help="Folder with simulation artifacts."),
    fmt: str = typer.Option("rcp_2025", help="Export format label."),
    out: Path = typer.Option(Path("./artifacts/export"), path_type=Path, help="Destination folder."),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable debug logging."),
):
    """Compress and package the pipeline outputs."""

    logger = configure_logger(verbose)
    extraction_path = extraction_dir / "extraction.json"
    kinematics_path = extraction_dir / "kinematics.json"
    simulation_path = simulation_dir / "simulation.json"

    if not extraction_path.exists():
        raise FileNotFoundError(f"Missing extraction.json in {extraction_dir}")
    if not simulation_path.exists():
        raise FileNotFoundError(f"Missing simulation.json in {simulation_dir}")

    with extraction_path.open(encoding="utf-8") as handle:
        extraction_data = json.load(handle)

    kine = serialization.load_kinematics(kinematics_path, logger)
    sim_channels = serialization.load_simulation(simulation_path, logger)

    extraction_result = extraction.ExtractionResult(
        skeleton=np.array(extraction_data.get("skeleton_points", [])),
        edges=np.array([]),
        metadata=extraction_data.get("metadata", {}),
    )
    bundle = serialization.ExportBundle(
        extraction=extraction_result,
        kinematics=kine,
        simulation=sim_channels,
    )
    manifest_path = serialization.export_bundle(bundle, out, fmt, logger)
    console.print(f"Exported bundle manifest at {manifest_path}")


if __name__ == "__main__":
    app()
