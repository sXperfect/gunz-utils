"""CSV and HTML export for process profiles."""

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

from __future__ import annotations

import base64
import csv
import html
import io
from pathlib import Path
from typing import Protocol

# =============================================================================
# LOCAL APPLICATION IMPORTS
# =============================================================================
from ..io import atomic_write
from .plot import plot_process_samples
from .process import ProcessProfile
from .report import format_process_profile


class _Figure(Protocol):
    """Minimal matplotlib Figure surface used for PNG rendering."""

    def savefig(self,
        fname: object,
        **kwargs: object,
    ) -> None:
        """Save the current figure to the given destination.

        Parameters
        ----------
        fname : object
            The output filename or file-like object.
        **kwargs : object
            Additional keyword arguments passed to the backend.
        """


def save_process_csv(
    profile: ProcessProfile,
    path: str | Path,
) -> None:
    """Write aggregate process-tree samples as portable CSV.

    Parameters
    ----------
    profile : ProcessProfile
        profile parameter.
    path : str | Path
        path parameter.
    """
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
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fields)
    writer.writeheader()
    for sample in profile.samples:
        writer.writerow({field: getattr(sample, field) for field in fields})
    atomic_write(path, buffer.getvalue(), encoding="utf-8")


def _figure_data_uri(
    figure: _Figure,
) -> str:
    """_figure_data_uri() function.

    Parameters
    ----------
    figure : _Figure
        figure parameter.

    Returns
    -------
    str
        The result of the operation.
    """
    buffer = io.BytesIO()
    figure.savefig(buffer, format="png", bbox_inches="tight")
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode()


def save_process_html(
    profile: ProcessProfile,
    path: str | Path,
) -> None:
    """Write a self-contained HTML profile report with embedded plots.

    Parameters
    ----------
    profile : ProcessProfile
        profile parameter.
    path : str | Path
        path parameter.
    """
    metrics = ["rss_bytes", "cpu_cores", "process_count", "threads"]
    images = []
    for metric in metrics:
        figure = plot_process_samples(profile, metric)
        images.append((metric, _figure_data_uri(figure)))
    summary = format_process_profile(profile)
    rows = "\n".join(
        f"<tr><td>{html.escape(line.split('|')[1].strip())}</td>"
        f"<td>{html.escape(line.split('|')[2].strip())}</td></tr>"
        for line in summary.splitlines()[2:]
        if line.startswith("|")
    )
    plots = "\n".join(
        f"<h2>{html.escape(name)}</h2><img src=\"{uri}\" alt=\"{html.escape(name)}\">"
        for name, uri in images
    )
    html_content = (
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
    atomic_write(path, html_content, mode="w", encoding="utf-8")


def export_benchmark_csv(results: list[dict[str, object]]) -> str:
    """Format benchmark results as a CSV string."""
    if not results:
        return ""
    keys: list[str] = list(results[0].keys())
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=keys)
    writer.writeheader()
    for r in results:
        writer.writerow(r)
    return buffer.getvalue()


def export_benchmark_json(results: list[dict[str, object]], indent: int = 2) -> str:
    """Format benchmark results as a formatted JSON string."""
    import json
    return json.dumps(results, indent=indent, default=str)


def format_summary_matrix(results: list[dict[str, object]]) -> str:
    """Format benchmark results as an ASCII matrix table."""
    if not results:
        return ""
    headers = [str(k) for k in results[0].keys()]
    rows = [[str(r.get(h, "")) for h in headers] for r in results]
    col_widths = [max(len(h), max((len(row[i]) for row in rows), default=0)) for i, h in enumerate(headers)]

    sep = "+-" + "-+-".join("-" * w for w in col_widths) + "-+"
    header_line = "| " + " | ".join(f"{h:<{w}}" for h, w in zip(headers, col_widths)) + " |"
    data_lines = [
        "| " + " | ".join(f"{val:<{w}}" for val, w in zip(row, col_widths)) + " |"
        for row in rows
    ]

    return "\n".join([sep, header_line, sep] + data_lines + [sep])


__all__ = [
    "export_benchmark_csv",
    "export_benchmark_json",
    "format_summary_matrix",
    "save_process_csv",
    "save_process_html",
]
