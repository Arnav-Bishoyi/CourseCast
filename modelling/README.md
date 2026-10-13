# Modelling handoff

- Sardor: audit grade history and produce a joinable prior-term feature table.
- Avaneesh: retrieve course descriptions and build the small embedding experiment.
- Feature Engineering: construct section-hour rows using observed interval endpoints.

Use stable term/course keys; term + CRN identifies sections. Never use future
closure status, future sibling status or future grades as forecast features.
Missing endpoints are not negative labels. Explicitly settle censoring, reopenings
and sampling intervals with Tanush before training. Demo snapshots are not training
data for a usable model. The planned forecaster is one LightGBM hazard classifier;
there is no trained model in this starter.

Optional dependencies: `python -m pip install -r modelling/requirements.txt`.
