# PlaNet-like Model Cache

This directory is reserved for the Laitoxx Photo Geolocation global mode.

The implementation uses GeoCLIP as a practical open PlaNet-like backend. At
runtime Laitoxx points `HF_HOME`, `HUGGINGFACE_HUB_CACHE`, `TORCH_HOME` and
`XDG_CACHE_HOME` into this directory so downloaded model weights and related
cache files stay inside the project tree.

The original Google PlaNet weights are not bundled here.
