import os
from pathlib import Path

_IS_LAMBDA = "AWS_LAMBDA_FUNCTION_NAME" in os.environ


def root() -> Path:
    """Get the project root directory.
    
    On Lambda, uses /tmp since the package directory is read-only.
    """
    if _IS_LAMBDA:
        return Path("/tmp")
    return Path(__file__).parent.parent.parent


def data_dir(fid: str = "") -> Path:
    """
    Get the data directory path.
    
    Args:
        fid: Optional subdirectory/file name within the data directory
    
    Returns:
        Path object pointing to the data directory or subdirectory
    """
    path = root() / "data"
    if fid:
        path = path / fid
    return path
