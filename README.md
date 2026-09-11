# Alok Ingots — Customer Portal

Customer portal for **Alok Ingots**, a stainless steel bright bar manufacturer and
exporter based in Mumbai, India.

Export customers log in to see their orders, shipment status, shipping documents
and tracking information in one place.

## Stack

| Layer    | Technology |
| -------- | ---------- |
| Backend  | FastAPI (Python) |
| Frontend | React |
| Database | PostgreSQL |
| Runtime  | Docker / Docker Compose |

## Local development

Start the PostgreSQL database:

```bash
cp .env.example .env      # then edit the values
docker compose up -d
```

Create the schema and insert the example order:

```bash
cd backend
.venv/Scripts/python.exe seed.py    # Windows
```

## Status

Early development — project scaffold only.

## Branching

- `main` — production-ready code
- `dev` — integration branch
- `feature/*` — all work happens here, then merges into `dev`
