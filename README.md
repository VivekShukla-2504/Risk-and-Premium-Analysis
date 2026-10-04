# Insurance Risk & Premium Analytics System

A full-stack portfolio project that applies **traditional actuarial measures** (claim frequency, severity, pure premium,
loss ratio, credibility, scenario analysis) to an insurance policy and claim file. No machine learning, no AI.

> **The data is synthetic and this is educational software, not production actuarial software.**
> Results are descriptive or scenario-based, never predictions or pricing advice. Assumptions are in
> [docs/DATA_AUDIT.md](docs/DATA_AUDIT.md) and on the **Methodology** page of the app.

```
React + Vite + Tailwind + Recharts + Axios   (frontend, port 5173)
        |  REST / JSON
FastAPI + Pydantic                           (backend, port 8000, Swagger at /docs)
        |
Analytics services (pandas + NumPy)          every number is calculated here, never in React
        |
MongoDB Atlas (optional)  ->  falls back to  ->  data/cleaned_insurance_data.csv
```

## Run it (about 5 minutes)

You need **Python 3.11+** and **Node.js 18+**.

**1. Backend** (terminal 1)

```bash
cd backend
python -m venv .venv
# macOS / Linux:   source .venv/bin/activate
# Windows (cmd):   .venv\Scripts\activate
# Windows (PowerShell): .venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Check it: open http://localhost:8000/docs (interactive API) and http://localhost:8000/api/health.
No `.env` is needed to start; the defaults use the cleaned CSV that ships in `backend/data/`.

**2. Frontend** (terminal 2)

```bash
cd frontend
npm install
npm run dev
```

Open **http://localhost:5173**.

If the page shows "Cannot reach the API", the backend is not running on port 8000, or you changed ports:
copy `frontend/.env.example` to `frontend/.env.local` and set `VITE_API_BASE_URL`, and add the frontend origin to
`CORS_ORIGINS` in `backend/.env`.

## Pages

| Page | What it shows |
|---|---|
| Dashboard | 8 KPIs and 10 charts, with Chart/Table switch on each |
| Portfolio analytics | Frequency, severity, pure premium and loss ratio by policy type, age band, gender; significance tests; actual vs expected |
| Claims analytics | Claim status, coverage vs claim size, claim-to-coverage ratio, severity distribution, loss ratio |
| Risk segmentation | Rule-based tiers (documented rules) tested against actual experience |
| Scenario analysis | Baseline, Optimistic, Stress and Custom compared side by side (table and charts), a step-by-step explanation of every calculation, and a sensitivity grid |
| Rate adequacy indication | Baseline credibility-weighted earned-premium indication by policy type, age band and gender at a selected target loss ratio |
| Methodology | Formula, numerator, denominator, assumptions and limitations of every metric; data-audit findings |

Filters (policy type, gender, age band, claim status, date range) apply to every page. **Export report** downloads CSV or JSON.

## API

All under `/api`. Every analytics response is `{ "meta": {...}, "data": {...} }`; `meta` carries the filters applied,
policies in scope, warnings and `rate_metrics_valid` (false when filters select on claim outcome, which makes
frequency and loss ratio meaningless).

| Endpoint | Purpose |
|---|---|
| `GET /health` | Service status and active data source |
| `GET /dashboard/summary` | KPIs, confidence intervals, filter options |
| `GET /analytics/policy-types`, `/age-bands` | Segment metrics, tests, actual vs expected |
| `GET /analytics/claims`, `/loss-ratio`, `/severity`, `/frequency` | Focused analyses |
| `GET /analytics/monthly-trends` | Claims per 100 policy-months in force |
| `GET /analytics/risk-segments` | Risk tiers and their test against experience |
| `GET /analytics/rate-indication?target_loss_ratio_pct=65` | Baseline rate adequacy indication by segment (target allowed from 30% to 100%) |
| `POST /analytics/scenario/compare` | Baseline, Optimistic, Stress and Custom side by side, with step-by-step calculations |
| `POST /analytics/scenario` | One scenario in depth: sensitivity grid, unranked assumption comparison, by policy type |
| `GET /analytics/export?section=...&format=csv\|json` | Downloadable reports; `section=rate-indication` also accepts `target_loss_ratio_pct` |
| `GET /methodology`, `GET /data-quality` | Definitions, rules, audit findings |

Filters: `policy_type`, `gender`, `age_band`, `claim_status`, `start_date`, `end_date`, `date_basis`.

## Tests

```bash
cd backend  && python -m unittest discover -s tests
cd frontend && npm test                                 # 10 tests for formatting, filters, errors, chart mapping
```

For the HTTP-level tests on the current Starlette release, install its TestClient transport with
`pip install "httpx2>=2.13.1"` in the backend environment.

## Optional: MongoDB Atlas

Put `MONGODB_URI` in `backend/.env` (never commit it), `pip install "pymongo[srv]"`, then
`python scripts/seed_mongodb.py`. The API reads MongoDB when reachable and silently falls back to the CSV otherwise
(`/api/health` shows which source is active).

## Scenario analysis (not a prediction)

Inputs (percent): claim frequency adjustment, claim severity adjustment, claim inflation, premium adjustment, plus an
assumed expense ratio and a target loss ratio. All scenarios use the observed portfolio as the baseline.

```
baseline claim cost   = policies x frequency x severity                      (= observed incurred claims)
adjusted frequency    = frequency x (1 + frequency adjustment)
adjusted severity     = severity x (1 + severity adjustment) x (1 + claim inflation)
adjusted claim cost   = policies x adjusted frequency x adjusted severity
adjusted premium      = earned premium x (1 + premium adjustment)
adjusted loss ratio   = adjusted claim cost / adjusted premium
```

Worked example (6-policy test portfolio: 4 claims, incurred 5,000, earned premium 3,500), Stress = +15% frequency,
+10% severity, +8% inflation, 0% premium: cost = 5,000 x 1.15 x 1.10 x 1.08 = 6,831; loss ratio = 6,831 / 3,500 = 195.2%.

Optimistic and Stress are **illustrative assumptions**, not estimated from the data and not forecasts. The app labels
them as such. Limits: no IBNR, claim development, trend or change in policy count; the underwriting margin
(1 - loss ratio - expense ratio) is illustrative and ignores investment income, reinsurance, capital and taxes.

## Key methodology decisions

* **Loss ratio = incurred claims / earned premium.** Incurred = Settled + Pending; earned premium is a pro-rata proxy
  because the file has no earned-premium column.
* **Claim frequency = claiming policies / policies.** Each policy has at most one claim, so this is an incidence rate.
* **"Rejected" rows carry no claim date or amount**, so a rejection rate is deliberately not reported.
* **Monthly counts follow policies in force**, so the trend is shown per policy-month of exposure.
* **Risk tiers use only information known before a claim** (age, coverage) to avoid circular reasoning, and are then
  tested; with this data the tiers are not supported by experience, and the app says so.

## Rate adequacy indication (not a scenario or recommendation)

The Rate Indication page uses the selected cohort's baseline experience, independently of the Scenario Analysis
sliders. For the overall portfolio and each policy-type, age-band and gender segment:

```
observed pure premium       = incurred claims / policies
credibility factor Z        = min(1, sqrt(segment claiming policies / 1,082))
indicated pure premium      = Z x segment observed pure premium
                            + (1 - Z) x filtered portfolio pure premium
indicated earned premium    = indicated pure premium / target loss ratio
indicated rate change (%)   = (indicated earned premium per policy
                               / current earned premium per policy - 1) x 100
```

The 1,082-claim threshold is the project's classical limited-fluctuation standard (90% probability and +/-5% error).
The complement is the filtered portfolio's observed pure premium, not an external prior; this simple claim-count blend
is not a Bühlmann model and does not give severity-specific credibility. Incurred claims are Settled paid plus Pending
outstanding; earned premium is the daily pro-rata proxy at the valuation date. The selected target loss ratio is the
claims share of earned premium; expenses, profit, taxes, reinsurance, capital, trend, development and IBNR are not
loaded separately. The target is bounded to 30%-100%.

The filtered-portfolio row is the unblended reference experience, so its credibility factor is not applicable (shown
as `n/a`); the 1,082-claim credibility factor applies to the segment indications blended against that reference.

Outcome-selected filters (`claim_status` or claim-date ranges) are rejected because they do not define a valid cohort
denominator. Empty portfolios, no-claim portfolios and groups with no current earned premium produce explicit
unavailable values instead of fabricated rate changes. Segment indications are separate comparisons against each
segment's average current earned premium per policy; do not add them across dimensions. The experience is synthetic,
so indications are descriptive and can be extreme or unstable.

## Layout

```
backend/app/{config.py, main.py, dependencies.py, routes/, schemas/, services/, utils/}
backend/{data/, scripts/, tests/}
frontend/src/{pages/, components/, hooks/, services/, utils/}
docs/{DATA_AUDIT.md, DATA_DICTIONARY.md}
```
