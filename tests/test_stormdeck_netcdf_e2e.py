import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"

netcdf4 = pytest.importorskip("netCDF4", reason="synthetic NetCDF end-to-end tests require netCDF4")


def write_grouped_cfradial(path: Path):
    import numpy as np
    from netCDF4 import Dataset

    with Dataset(path, "w") as ds:
        sweep = ds.createGroup("sweep_0")
        sweep.createDimension("ray", 3)
        sweep.createDimension("gate", 4)
        rng = sweep.createVariable("range", "f4", ("gate",))
        rng.units = "meters"
        rng[:] = np.array([1000.0, 2000.0, 3000.0, 4000.0], dtype="float32")
        sweep.createVariable("azimuth", "f4", ("ray",))[:] = np.array([180.0, 181.0, 182.0], dtype="float32")
        sweep.createVariable("elevation", "f4", ("ray",))[:] = np.array([0.5, 0.5, 0.6], dtype="float32")
        sweep.createVariable("time", "f4", ("ray",))[:] = np.array([0.0, 1.0, 2.0], dtype="float32")
        ref = sweep.createVariable("reflectivity", "f4", ("ray", "gate"), fill_value=-9999.0)
        ref.units = "dBZ"
        ref[:] = np.array([[5.0, 12.0, -999.0, 24.0], [30.0, 35.0, 40.0, 45.0], [50.0, -9999.0, 55.0, 60.0]], dtype="float32")


def test_katd_replay_export_reads_synthetic_grouped_netcdf(tmp_path):
    src = tmp_path / "KATD_Base_Data_20260123_205908_830894500.nc"
    out = tmp_path / "bundle"
    write_grouped_cfradial(src)

    result = subprocess.run(
        [sys.executable, str(SCRIPTS / "stormdeck_katd_replay_export.py"), str(src), "--out", str(out), "--fields", "REF", "--no-render"],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )

    manifest = json.loads((out / "case_manifest.json").read_text(encoding="utf-8"))
    stats = json.loads(next(out.glob("frames/*/field_stats.json")).read_text(encoding="utf-8"))
    assert manifest["case_id"] == "KATD_20260123_205908"
    assert stats["REF"]["valid_gate_count"] == 10
    assert stats["REF"]["missing_gate_count"] == 2
    assert "case_manifest" in result.stdout


def test_single_frame_and_3d_renderers_accept_synthetic_grouped_netcdf(tmp_path):
    src = tmp_path / "sample.nc"
    write_grouped_cfradial(src)

    single_out = tmp_path / "single"
    three_d_out = tmp_path / "three_d"
    subprocess.run(
        [sys.executable, str(SCRIPTS / "stormdeck_single_frame_preview.py"), str(src), "--out", str(single_out), "--field", "REF", "--size", "180", "--gate-stride", "2"],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    subprocess.run(
        [sys.executable, str(SCRIPTS / "stormdeck_3d_frame_render.py"), str(src), "--out", str(three_d_out), "--field", "REF", "--width", "240", "--height", "180", "--gate-stride", "2"],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )

    assert any(single_out.glob("*.png"))
    assert any(three_d_out.glob("*.png"))
    assert any(three_d_out.glob("*.json"))
