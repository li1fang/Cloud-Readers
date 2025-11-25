"""Typer CLI entry point for Cloud Readers."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import click
import numpy as np
from rich.console import Console
from rich.table import Table

from . import extraction, ingestion, kinematics, serialization, simulation

console = Console()
app = click.Group(help="Cloud Readers: resurrect biomechanics from static art")


def configure_logger(verbose: bool) -> logging.Logger:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    return logging.getLogger("cloud-readers")


@app.command()
@click.option("--source", required=True, type=click.Path(exists=True, readable=True, path_type=Path), help="Source artwork to ingest.")
@click.option("--device", default="generic", show_default=True, help="Device profile label.")
@click.option("--style", default="neutral", show_default=True, help="Artistic intent for metadata tagging.")
@click.option(
    "--out",
    default=Path("./artifacts/extraction"),
    show_default=True,
    type=click.Path(path_type=Path),
    help="Directory to store intermediate outputs.",
)
@click.option("--verbose", "-v", is_flag=True, default=False, help="Enable debug logging.")
def extract(source: Path, device: str, style: str, out: Path, verbose: bool) -> None:
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
@click.option(
    "--input-dir",
    required=True,
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="Directory containing kinematics.json.",
)
@click.option("--physics-engine", default="internal", show_default=True, help="Physics backend name.")
@click.option(
    "--out",
    default=Path("./artifacts/simulation"),
    show_default=True,
    type=click.Path(path_type=Path),
    help="Directory to store simulated data.",
)
@click.option("--verbose", "-v", is_flag=True, default=False, help="Enable debug logging.")
def simulate(input_dir: Path, physics_engine: str, out: Path, verbose: bool) -> None:
    """Generate IMU-like channels from extracted kinematics."""

    logger = configure_logger(verbose)
    kinematics_path = input_dir / "kinematics.json"
    if not kinematics_path.exists():
        raise FileNotFoundError(f"Missing kinematics.json in {input_dir}")

    kine = serialization.load_kinematics(kinematics_path, logger)
    simulated = simulation.simulate_motion(kine, physics_engine=physics_engine, logger=logger)
    serialization.export_simulation(simulated, out, logger)

    console.print(f"Simulated data written to {out}")


@app.command()
@click.option(
    "--extraction-dir",
    required=True,
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="Folder with extraction artifacts.",
)
@click.option(
    "--simulation-dir",
    required=True,
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="Folder with simulation artifacts.",
)
@click.option("--fmt", default="rcp_2025", show_default=True, help="Export format label.")
@click.option(
    "--out",
    default=Path("./artifacts/export"),
    show_default=True,
    type=click.Path(path_type=Path),
    help="Destination folder.",
)
@click.option("--verbose", "-v", is_flag=True, default=False, help="Enable debug logging.")
def export(extraction_dir: Path, simulation_dir: Path, fmt: str, out: Path, verbose: bool) -> None:
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

    extraction_metadata = dict(extraction_data.get("metadata", {}))
    extraction_metadata.setdefault("source", str(extraction_path.parent))

    extraction_result = extraction.ExtractionResult(
        skeleton=np.array(extraction_data.get("skeleton_points", [])),
        edges=np.array([]),
        metadata=extraction_metadata,
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
