# StormDeck

StormDeck is a game-engine-powered 4D severe-weather interface concept for phased-array radar, NEXRAD, and radar-derived storm data.

## Posted spec

- [Interactive ATD initial spec](stormdeck-atd-initial-spec.html)

This first public artifact focuses on NOAA/NSSL Advanced Technology Demonstrator data output, especially public `KATD` CfRadial 1 NetCDF files from the NSSL THREDDS archive.

## MVP framing

StormDeck v0 starts with archived replay data, not live PAR access. It should load a public ATD case, preserve true sector geometry, render time-scrubbable reflectivity and velocity, support slicing, show storm motion and scan age, include at least one semantic storm object, and expose a “what changed in the last 60 seconds” panel.
