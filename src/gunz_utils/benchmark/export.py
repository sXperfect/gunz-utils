"""CSV and HTML export for process profiles."""

from __future__ import annotations

import base64
import csv
import io
from pathlib import Path
from typing import Protocol

from .plot import plot_process_samples
from .process import ProcessProfile
from .report import format_process_profile


class _Figure(Protocol):
    """Minimal matplotlib Figure surface used for PNG rendering."""

    def savefig(self, fname: object, **kwargs: object) -> None: ...


def save_process_csv(profile: ProcessProfile, path: str | Path) -> None:
    """Write aggregate process-tree samples as portable CSV."""
    fields = [
        "elapsed",
        "process_count",
        "threads",
        "cpu_user_seconds",
        "cpu_system_seconds",
        "rss_bytes",
        "pss_bytes",
        "private_bytes",
        "read_bytes",
        "write_bytes",
        "minor_faults",
        "major_faults",
        "voluntary_context_switches",
        "involuntary_context_switches",
    ]
    with Path(path).open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for sample in profile.samples:
            writer.writerow({field: getattr(sample, field) for field in fields})


def _figure_data_uri(figure: _Figure) -> str:
    buffer = io.BytesIO()
    figure.savefig(buffer, format="png", bbox_inches="tight")
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode()


def save_process_html(profile: ProcessProfile, path: str | Path) -> None:
    """Write a self-contained HTML profile report with embedded plots."""
    metrics = ["rss_bytes", "cpu_cores", "process_count", "threads"]
    images = []
    for metric in metrics:
        figure = plot_process_samples(profile, metric)
        images.append((metric, _figure_data_uri(figure)))
    summary = format_process_profile(profile)
    rows = "\n".join(
        f"<tr><td>{line.split('|')[1].strip()}</td>"
        f"<td>{line.split('|')[2].strip()}</td></tr>"
        for line in summary.splitlines()[2:]
        if line.startswith("|")
    )
    plots = "\n".join(
        f"<h2>{name}</h2><img src=\"{uri}\" alt=\"{name}\">"
        for name, uri in images
    )
    html = (
        "<!doctype html><meta charset=\"utf-8\">"
        "<title>Process profile</title>"
        "<style>body{font-family:sans-serif;max-width:1100px;margin:2rem auto;}"
        "table{border-collapse:collapse}td{padding:.3rem .8rem;border:1px solid #ccc;}"
        "img{max-width:100%;height:auto}</style>"
        "<h1>Process profile</h1><table>"
        + rows
        + "</table>"
        + plots
    )
    Path(path).write_text(html, encoding="utf-8")


__all__ = ["save_process_csv", "save_process_html"]
