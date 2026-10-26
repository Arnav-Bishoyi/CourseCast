# CourseCast: what a good forecast is (draft)

**Task.** For each course-section and upcoming term, output P(course closes), meaning it hits capacity before registration ends. This is a probability, not a yes/no.

**What counts as good.** We judge forecasts on honesty first and sharpness second.
1. **Calibrated.** Among all courses we label "70% likely to close", about 70% should close. We check this with reliability diagrams (quantile bins, with bin counts shown so thin bins are not over-read) and report expected calibration error.
2. **Accurate by Brier score.** The primary metric is the Brier score, the mean of (p − outcome)². It rewards both calibration and sharpness, and lower is better. We also report Brier skill score against the baseline: 1 − Brier_model / Brier_baseline. A forecast is only "good" if that is clearly above 0.
3. **Useful.** Probabilities far from the base rate must be right when they are far. A model that always says 50% can be calibrated and still be worthless.

**Baseline.** "This course closed in X% of past terms": for each course, the fraction of its earlier terms in which it closed. Courses with no history, or only one or two terms, fall back to the department-level rate, then the global rate. The baseline is strong, because closure is very persistent, so beating it is the real bar. Every metric is reported next to it.

**Splitting by time.** Random splits leak the future, because the same course in neighbouring terms is near-duplicate data. Instead:
- Split by term. Train on terms ≤ T, validate on T+1, test on T+2 and later. The test set is never touched during tuning.
- Use rolling-origin evaluation: repeat with T moving forward (for example, Fall 2021, 2022, 2023 as successive test terms) and report the mean and spread of the metrics.
- Build features, including the baseline's X%, using only data available at forecast time. For a test term, X comes from earlier terms only. Fit any recalibration (Platt or isotonic) on the validation term, never on the test term.
- Keep each term whole: all sections in a term go to the same side of the split.

