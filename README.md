# FinLend — Voice-Enabled Peer-to-Peer Micro-Lending Platform

**Academic prototype** built for a final-year Information Technology project
(Chaitanya Bharathi Institute of Technology, Batch CBIT/IT/2026-27/IT2/220).

> ⚠️ **This system uses simulated financial transactions and synthetic data
> only.** It does not process real money, issue real loans, or connect to
> any real bank. Blockchain amounts are simulated units for demonstration.

Extends the base paper *"Financing a Low-Carbon Supply Chain Through Online
Peer-to-Peer Lending"* (Gao et al., IEEE TEM 2024) by applying its P2P
financing concept to **financial inclusion**: call/voice-based access,
behavior-based credit scoring, and blockchain-backed transparency for
underserved borrowers without smartphones or formal credit histories.

## Architecture

```
Angular (Tailwind, glassmorphism UI)
        │  HTTPS / JSON
        ▼
FastAPI backend  ── MongoDB (users, loans, fundings, repayments, credit history)
        │
        ├── Credit Engine (rule-based behavioral scoring)
        ├── ML Risk Classifier (scikit-learn RandomForest)
        └── Blockchain Service (web3.py) ── Hardhat local node ── LoanRegistry.sol
```

```
Register → Initial credit score/limit → Voice loan request → Intent detection
→ Credit/risk evaluation → Approval → P2P marketplace → Multi-lender funding
→ Blockchain funding event → Loan ACTIVE → Repayment → Blockchain repayment
event → Credit score update → Borrowing limit update → Dashboards refresh
```

## Repository layout

```
backend/      FastAPI app, ML pipeline, seed scripts, tests (+ Dockerfile)
blockchain/   Hardhat project: LoanRegistry.sol, deploy script, contract tests (+ Dockerfile)
frontend/     Angular 18 standalone app (Tailwind CSS, glassmorphism) (+ Dockerfile)
docker-compose.yml   Root Docker Compose file wiring all services together
.env.example         Root environment template for Docker Compose
```

## Quick start (Docker — recommended)

Docker is now the standard, recommended way to run FinLend. You only need
**Docker Desktop** (macOS/Windows) or **Docker Engine + Compose v2** (Linux)
installed on your machine — no Python, Node.js, Angular CLI, MongoDB, or
Hardhat needed locally.

```bash
git clone <repository>
cd FinLend
cp .env.example .env      # review/adjust values if needed
docker compose up --build
```

That single command builds and starts MongoDB, the Hardhat blockchain node
(with automatic contract deployment), the FastAPI backend, and the Angular
frontend, wired together over Docker's internal network.

- **Frontend:** http://localhost:4200
- **Backend / API:** http://localhost:8000/api (health check: http://localhost:8000/api/health)
- **Blockchain RPC:** http://localhost:8545

Stop the stack (data is preserved):

```bash
docker compose down
```

Start it again later without losing MongoDB data:

```bash
docker compose up
```

Rebuild after pulling changes or editing a Dockerfile/dependency file:

```bash
docker compose up --build
```

View logs:

```bash
docker compose logs -f            # all services
docker compose logs -f backend    # one service
```

**Seeding demo data / training the ML model** (optional, one-time, run
while the stack is up):

```bash
docker compose exec backend python scripts/seed_db.py --reset
docker compose exec backend python -m app.ml.train_model
```

## Quick start (manual/legacy setup)

> This manual, per-service setup is kept for reference. **New contributors
> should use the Docker workflow above.**

```bash
# 1. Blockchain (terminal 1)
cd blockchain && npm install && npx hardhat node

# 2. Deploy contract (terminal 2)
cd blockchain && npx hardhat run scripts/deploy.js --network localhost
# copy the printed address into backend/.env as CONTRACT_ADDRESS

# 3. Backend (terminal 3)
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
python -m app.ml.train_model
python scripts/seed_db.py --reset
uvicorn app.main:app --reload --port 8000

# 4. Frontend (terminal 4)
cd frontend
npm install
npm start
```

Then open http://localhost:4200 and log in with a seeded demo account

## Technology stack (approved, preserved from Review-1)

- **Frontend:** Angular, HTML/CSS, Tailwind CSS
- **Backend:** Python, FastAPI
- **Database:** MongoDB
- **Voice:** Speech-to-text / Intent detection / Text-to-speech (demo-mode
  local pipeline by default; pluggable for real providers)
- **Blockchain:** Solidity, Hardhat, Ethereum-compatible network, smart contracts
- **Credit scoring:** Python, scikit-learn, repayment-based behavioral scoring
