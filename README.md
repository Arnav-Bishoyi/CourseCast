# CourseCast

CourseCast is a forecasting tool designed to help UIUC students make better decisions during course registration.

Instead of only showing whether a section is open **right now**, CourseCast aims to answer a more useful question:

> **What is the probability that this section will still be open when I register?**

By combining current course availability with historical course data, CourseCast will estimate how likely individual sections are to remain available and show students how enrollment behavior changes over time.

---

## Features

CourseCast is being built to provide:

- **Section availability forecasts** — estimated probability that a section will still be open at a student's registration time
- **Section comparisons** — compare availability across multiple sections of the same course
- **Historical trends** — visualize how courses and sections have filled in previous terms
- **Instructor history** — provide additional historical context for individual sections
- **Fill curves** — show how section availability changes as registration progresses
- **Cold-start support** — use course similarity to help make predictions for courses with limited historical data
- **Calibrated probabilities** — ensure that predicted probabilities correspond meaningfully to real outcomes

Example:

```text
CS 341 AL1
82% chance of still being open
```

---

## How It Works

CourseCast is organized around four main components.

### 1. Data Pipeline

The data pipeline collects course and section information from the UIUC Course Explorer API.

Initial work focuses on collecting information such as:

- Course sections
- CRNs
- Enrollment status
- Cross-listed sections
- Historical changes in section availability

The collector is designed to periodically record registration data so that CourseCast can learn how sections fill over time.

Technologies being explored include:

- Python
- `httpx`
- `lxml`
- PostgreSQL
- Scheduled data collection

---

### 2. Modeling

The forecasting model will use historical course and registration information to estimate whether a section is likely to remain available.

The initial modeling direction includes:

- Tabular historical data
- pandas for data analysis
- LightGBM
- Time-based train/test splits
- Careful prevention of data leakage

One of the core prediction problems is:

```text
Will this section close within the next hour?
```

These predictions can then contribute to a student's estimated probability that a section will remain open by their registration time.

---

### 3. Cold-Start Course Similarity

Some courses may not have enough historical registration data to make a strong prediction.

CourseCast is exploring text embeddings as a way to find historically similar courses based on catalog descriptions.

The initial approach uses:

```text
sentence-transformers
all-MiniLM-L6-v2
cosine similarity
```

If a new course resembles several existing courses, their historical enrollment behavior may provide useful information for the forecast.

---

### 4. Evaluation

CourseCast predictions should not only be accurate — their probabilities should also be meaningful.

For example, among sections given an **80% probability of remaining open**, roughly 80% should actually remain open.

Evaluation will include:

- Calibration
- Brier score
- Reliability diagrams
- Time-based evaluation

A simple historical baseline will also be used:

> **This course remained open in X% of past terms.**

The model should improve on this baseline while remaining well calibrated.

---

## Frontend

The first CourseCast interface will be prototyped using **Streamlit**.

The application is currently planned around three primary screens:

### Input

Students provide information such as:

- Registration time ticket
- Courses or sections they are considering

### Results

CourseCast shows the predicted availability of each section.

Example:

```text
CS 341 AL1 — 82% chance still open
CS 341 AL2 — 61% chance still open
CS 341 AD1 — 37% chance still open
```

### Section Detail

A detailed section page may include:

- Predicted availability
- Historical fill curve
- Instructor history
- Historical registration behavior

Plotly is being explored for interactive visualizations.

---

## Tech Stack

### Data & Backend

- Python
- httpx
- lxml
- PostgreSQL
- pandas

### Machine Learning

- LightGBM
- scikit-learn
- sentence-transformers

### Frontend & Visualization

- Streamlit
- Plotly

### Development

- Git
- GitHub
- Pull requests for contributions

---

## Project Structure

The repository is still evolving, but development is organized around the major parts of CourseCast:

```text
CourseCast/
│
├── data/            # Data files and intermediate datasets
├── explore/         # Experiments, notebooks, and exploratory work
├── src/             # Main CourseCast source code
├── frontend/        # Streamlit application
├── models/          # Modeling and evaluation code
└── README.md
```

The exact structure may change as the project develops.

---

## Getting Started

### Prerequisites

Install:

- Python 3.11+
- Git
- A code editor such as VS Code

### Clone the Repository

```bash
git clone <repository-url>
cd CourseCast
```

### Create a Virtual Environment

```bash
python -m venv .venv
source .venv/bin/activate
```

On Windows:

```bash
.venv\Scripts\activate
```

### Install Dependencies

Once the project dependency file is available:

```bash
pip install -r requirements.txt
```

---

## Development Workflow

1. Pull the latest changes.
2. Create a branch for your work.
3. Make and test your changes.
4. Push your branch.
5. Open a pull request.

Example:

```bash
git checkout -b feature/my-feature
git add .
git commit -m "Add my feature"
git push origin feature/my-feature
```

Please use pull requests rather than pushing experimental work directly to the main branch.

Exploratory scripts and notebooks can be placed in:

```text
explore/
```

---

## Current Development Areas

The team is currently working across four areas:

| Area | Focus |
| --- | --- |
| Data Pipeline | Collect and store Course Explorer registration data |
| Modeling | Build section-availability forecasting models |
| Evaluation | Measure accuracy and probability calibration |
| Frontend | Design and prototype the student-facing application |

---

## Project Goal

Course registration often forces students to make decisions with incomplete information.

A section being open today does not tell a student whether it will still be open when their time ticket begins.

CourseCast aims to turn historical and live registration data into a simple answer:

> **How likely am I to actually get this section?**

The goal is to make registration planning more informed, transparent, and data-driven.

---

## Status

🚧 **CourseCast is currently under active development.**

The data collection, modeling, evaluation, and frontend systems are being developed in parallel.

---

## Contributing

Team members should:

- Keep changes focused
- Use feature branches
- Submit code through pull requests
- Document experiments clearly
- Avoid committing secrets, credentials, or API keys

For exploratory work, include enough context for another team member to reproduce your results.

---

## License

License information will be added as the project develops.
