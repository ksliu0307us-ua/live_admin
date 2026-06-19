# Life Admin Assistant — Subscription & Refund Assistant POC

An AI-powered tool that helps you find wasted money and missed opportunities by analyzing receipts, bills, subscriptions, and order emails.

Paste or upload an email/receipt, and the system will:
- Extract structured details (merchant, amount, dates, policies)
- Generate action cards (cancel, return, refund, price alert)
- Draft ready-to-send emails for each action

## Quick Start

### Backend

```bash
cd backend
python -m venv venv
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

The frontend runs at `http://localhost:3000`, the backend API at `http://localhost:8000`.

### Configuration

Copy `backend/.env.example` to `backend/.env`:

```bash
cp backend/.env.example backend/.env
```

- **Without an OpenAI API key**: The app runs in mock mode with realistic canned responses. Perfect for demos.
- **With an OpenAI API key**: Set `OPENAI_API_KEY` in `.env` for real LLM-powered extraction.

### Sample Inputs

The `samples/` folder contains realistic email texts you can paste into the app for testing:

- `netflix_renewal.txt` — Subscription renewal reminder
- `amazon_order.txt` — Order confirmation with return window
- `spotify_trial.txt` — Free trial ending soon
- `warranty_email.txt` — AppleCare+ warranty expiring
- `price_increase.txt` — YouTube Premium price hike

> **Privacy note**: When using real LLM mode, pasted text is sent to OpenAI for processing. Do not paste emails containing sensitive financial data (account numbers, SSNs, etc.) during development. Mock mode keeps everything local.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js, TypeScript, Tailwind CSS |
| Backend | FastAPI, Python, Pydantic, SQLAlchemy |
| Database | SQLite (local POC) |
| AI | OpenAI GPT-4o-mini (or mock fallback) |
