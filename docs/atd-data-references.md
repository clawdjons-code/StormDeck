# NSSL Advanced Technology Demonstrator (ATD) Data References

StormDeck's phased-array radar path should treat the NOAA/NSSL **Advanced Technology Demonstrator (ATD)** as the initial concrete PAR target. ATD is a single-face, S-band, dual-polarization phased-array weather radar in Norman, Oklahoma, operated by NOAA/NSSL with OU/CIWRO involvement.

## Operational context

The CIWRO story about the April 28 Caney, Oklahoma EF-2 tornado identifies the ATD as the PAR source used by NWS Norman forecasters during warning operations when KTLX had technical issues.

- Article: <https://www.ou.edu/ciwro/news/articles/2026/forecasters-rely-on-phased-array-radar-for-tornado-warning>
- Radar: NOAA/NSSL Advanced Technology Demonstrator (ATD), also appearing as `KATD` in data files.
- Operational claim to preserve in product narrative: fast PAR updates let forecasters watch storm evolution instead of mentally interpolating between slower NEXRAD scans.

## Primary technical/data sources

### NSSL ATD overview

- URL: <https://www.nssl.noaa.gov/tools/radar/atd/>
- Use for: radar identity, hardware overview, PAR capability framing.
- Key facts:
  - First full-scale S-band dual-polarization phased-array radar built specifically for weather observations.
  - Planar/single-face array with 76 panels and 4,864 radiating elements.
  - Approximate 90 degree field of view.
  - Research purpose: evaluate polarimetric performance, calibration, data quality, and faster phased-array scanning for future weather radar systems.

### Public NSSL THREDDS ATD archive

- Catalog HTML: <https://data.nssl.noaa.gov/thredds/catalog/RRDD/ATD/catalog.html>
- Catalog XML: <https://data.nssl.noaa.gov/thredds/catalog/RRDD/ATD/catalog.xml>
- Use for: public archived ATD case discovery and data download.
- Observed top-level public folders:
  - `2019/`
  - `2020/`
  - `2023/`
  - `PSU_Task3/`
  - `TTU_Task3/`
- Observed 2023 case-date folders include `0428`, `0510`, and `0511`.
- Common per-date subfolders:
  - `cfrad1/` — CfRadial 1 NetCDF files.
  - `nexrad/` — NEXRAD MSG31-like raw files.
- Archive caveat: data are minimally quality controlled and may include artifacts related to the experimental nature of the system.

Example CfRadial file names:

```text
cfrad.20230428_162022.548_to_20230428_162041.283_KATD_PPI.nc
cfrad.20230510_184115.441_to_20230510_184238.693_KATD_PPI.nc
```

Example NEXRAD/MSG31-like file names:

```text
ATD20230428162022.0.raw
ATD20230510184115.0.raw
KATD20230511143253.0.raw
```

### CfRadial documentation

- URL: <https://ncar.github.io/CfRadial/>
- Use for: NetCDF radial-coordinate conventions.
- ATD public archive says data are available as **CfRadial 1**. StormDeck should implement CfRadial 1 ingest first.

### ATD System Testing Summary Report

- URL: <https://www.nssl.noaa.gov/publications/par_reports/ATD-System-Testing-Summary-Report.pdf>
- Use for: emitted data classes, base variables, system/QC caveats.
- Important finding: ATD produces two major internal data classes:
  1. Raw received signals / I/Q data.
  2. Radar-variable/base data.
- Base radar variables identified in the report:
  - Reflectivity: `Z`, `dBZ`.
  - Radial velocity: `V`, m/s.
  - Spectrum width: `W`, m/s.
  - Differential reflectivity: `ZDR`, dB.
  - Specific differential phase: `KDP`, deg/km.
  - Correlation coefficient: `RHO` / `RHOHV`, unitless.

### 2023 ATD data collection NOAA technical memo

- Landing page: <https://repository.library.noaa.gov/view/noaa/65706>
- DOI: <https://doi.org/10.25923/4v1r-yq31>
- Use for: 2023 archive context, case portfolio, scan strategies, severe-weather examples.
- Key implications:
  - ATD operated in stationary pencil-beam mode with at most about a 90 degree azimuthal field of view.
  - Research scan strategies include rapid low-level revisits and dense vertical sampling for tornadic supercells, QLCS events, winter weather, and downbursts.
  - Do not assume WSR-88D VCP elevation lists or update cadence.

### ATD polarimetric calibration report

- URL: <https://www.nssl.noaa.gov/publications/par_reports/NSSL%20Follow-On%20ATD%20Calibration%20Report%20Sept%202023.pdf>
- Use for: calibration/QC caveats, dual-pol bias issues, steering-angle effects.
- Key implications:
  - Planar polarimetric phased-array radar measurements vary with electronic steering angle.
  - Calibration/bias correction metadata should be preserved where available.
  - ZDR and phase-related products need provenance/QC treatment.

## Verified sample CfRadial structure

Sample file inspected:

```text
https://data.nssl.noaa.gov/thredds/fileServer/RRDD/ATD/2023/0428/cfrad1/cfrad.20230428_162022.548_to_20230428_162041.283_KATD_PPI.nc
```

Global metadata observed:

```text
Conventions: CF/Radial instrument_parameters
version: 1.3
instrument_name: KATD
```

Dimensions observed:

```text
time: 206 rays
range: 1964 gates
sweep: 2
```

Geometry variables observed:

```text
time
range
azimuth
elevation
sweep_number
fixed_angle
sweep_start_ray_index
sweep_end_ray_index
sweep_mode
latitude
longitude
altitude
time_coverage_start
time_coverage_end
volume_number
```

Field variables observed:

```text
reflectivity                  units: dBZ
velocity                      units: meters_per_second
spectrum_width                units: meters_per_second
differential_reflectivity     units: dB
differential_phase            units: degrees
cross_correlation_ratio       units: ratio
```

Sample geometry observed:

```text
latitude: 35.236259
longitude: -97.463692
altitude: 369 m
azimuth coverage: about 270.3° to 359.7°
elevation coverage: about 0.5° to 0.9°
range spacing: 225 m
max range: about 442 km
```

## StormDeck ingest decision

Primary v0 PAR ingest target:

```text
NSSL THREDDS catalog → ATD CfRadial 1 NetCDF → radial geometry normalization → render-ready fields
```

Secondary/future ingest path:

```text
ATD NEXRAD MSG31/raw → existing Level II/Archive II decoder path, after compatibility testing
```

Do **not** start with raw/IQ for StormDeck MVP. Raw/IQ matters for radar engineering research, but base-data CfRadial is the practical path for visualization.

## Required ATD-aware parser behavior

- Use metadata-driven sweep/ray/range geometry.
- Do not assume 360° azimuth coverage.
- Do not assume fixed NEXRAD VCPs.
- Support irregular scan durations and revisit intervals.
- Preserve start/end timestamps per file and per sweep where possible.
- Preserve data source, instrument name, archive URL, QC caveats, and calibration/provenance metadata.
- Expose field availability per volume; do not require every dual-pol field in every file.
- Handle stale/missing THREDDS files gracefully; catalog entries may fail at download time.

## Field alias map

StormDeck should resolve multiple source variable names into canonical internal names:

```json
{
  "reflectivity": ["reflectivity", "DBZ", "ZH", "Z"],
  "radial_velocity": ["velocity", "VEL", "VR", "radial_velocity", "V"],
  "spectrum_width": ["spectrum_width", "WIDTH", "SW", "W"],
  "differential_reflectivity": ["differential_reflectivity", "ZDR"],
  "differential_phase": ["differential_phase", "PHIDP", "PhiDP"],
  "cross_correlation_ratio": ["cross_correlation_ratio", "RHOHV", "rhoHV", "RHO"],
  "specific_differential_phase": ["specific_differential_phase", "KDP"]
}
```

## Product/UX caveats to carry forward

- Label ATD as **research PAR data**, not operational NEXRAD.
- Always show source, scan time, scan age, scan duration, sweep/elevation, field name, and QC/provenance caveats.
- Clearly render the scan sector/coverage footprint so users do not infer data where the radar did not sample.
- Distinguish observed base radar fields from derived/AI/semantic storm objects.
- Preserve the phrase-level demo narrative: **watch the storm evolve, not jump**.

## Caney 2026 case availability note

The CIWRO article references the April 28 Caney, Oklahoma EF-2 tornado warning event and ATD use in operations. The checked public THREDDS catalog exposed ATD data for 2019, 2020, and 2023, but no public 2026 folder was observed at the time of review. StormDeck v0 should start with public 2023 ATD cases while keeping the exact 2026 Caney dataset as a request/access target through NSSL/CIWRO if needed.
