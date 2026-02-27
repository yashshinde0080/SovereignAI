"""CLI Theme"""
from rich.theme import Theme

THEME = Theme({
    "info": "cyan",
    "warning": "yellow",
    "error": "red bold",
    "success": "green",
    "primary": "blue",
    "secondary": "magenta",
    "muted": "dim",
    
    # Model states
    "model.loaded": "green",
    "model.loading": "yellow",
    "model.error": "red",
    
    # Modes
    "mode.fullram": "cyan",
    "mode.layerstream": "yellow",
    "mode.auto": "green",
    
    # Metrics
    "metric.good": "green",
    "metric.warning": "yellow",
    "metric.critical": "red",
})


# Color palette
COLORS = {
    "background": "#0f172a",
    "foreground": "#e2e8f0",
    "primary": "#3b82f6",
    "secondary": "#8b5cf6",
    "success": "#22c55e",
    "warning": "#f59e0b",
    "error": "#ef4444",
    "muted": "#64748b"
}