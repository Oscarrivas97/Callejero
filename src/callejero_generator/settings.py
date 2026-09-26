"""Small validated subset of generation settings used by this implementation stage."""

from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass(frozen=True)
class QualitySettings:
    minimum_espacios: int
    min_advantage_ratio: float
    min_advantage_seconds: float


@dataclass(frozen=True)
class OSMSettings:
    pbf_path: Path
    source_url: str
    sha256: str
    snapshot_date: str


def load_quality_settings(path: str | Path) -> QualitySettings:
    with Path(path).open(encoding="utf-8") as handle:
        config = yaml.safe_load(handle)
    try:
        settings = QualitySettings(
            minimum_espacios=int(config["projection"]["minimum_displayed_espacios"]),
            min_advantage_ratio=float(config["fastest_route"]["min_advantage_ratio"]),
            min_advantage_seconds=float(config["fastest_route"]["min_advantage_seconds"]),
        )
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError(f"Invalid quality settings in {path}") from error
    if settings.minimum_espacios < 1 or settings.min_advantage_ratio < 0 or settings.min_advantage_seconds < 0:
        raise ValueError("Quality thresholds must be non-negative and minimum Espacios positive")
    return settings


def load_source_paths(path: str | Path) -> dict[str, Path]:
    with Path(path).open(encoding="utf-8") as handle:
        config = yaml.safe_load(handle)
    try:
        return {key: Path(config["sources"][key])
                for key in ("espacios_pdf", "hitos_pdf", "sample_exam_pdf")}
    except (KeyError, TypeError) as error:
        raise ValueError(f"Invalid source paths in {path}") from error


def load_speed_defaults(path: str | Path) -> dict[str, float]:
    with Path(path).open(encoding="utf-8") as handle:
        config = yaml.safe_load(handle)
    try:
        speeds = {str(highway): float(speed) for highway, speed in config["speed_defaults_kmh"].items()}
    except (AttributeError, KeyError, TypeError, ValueError) as error:
        raise ValueError(f"Invalid speed defaults in {path}") from error
    if not speeds or any(speed <= 0 for speed in speeds.values()):
        raise ValueError("Every highway speed default must be positive")
    return speeds


def load_osm_settings(path: str | Path) -> OSMSettings:
    with Path(path).open(encoding="utf-8") as handle:
        config = yaml.safe_load(handle)
    try:
        osm = config["osm"]
        return OSMSettings(Path(osm["pbf_path"]), str(osm["source_url"]),
                           str(osm["sha256"]), str(osm["snapshot_date"]))
    except (KeyError, TypeError) as error:
        raise ValueError(f"Invalid OSM settings in {path}") from error
