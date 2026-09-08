# KutLynk Supabase Backend

This is the Supabase-backed replacement for `backend-fastapi`. It keeps the same frontend API paths and response envelope.

## Setup

1. Run `SUPA.BASE.sql` in the Supabase SQL editor.
2. Copy `.env.example` to `.env`.
3. Set `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY`.
4. Install the packages listed in `requirements.txt` in your Python environment.

## Run

```powershell
uvicorn Main:app --reload --host 127.0.0.1 --port 3333
```

The service uses the Supabase service-role key server-side. Never expose that key to the frontend.

## API groups

- `/api/auth/*`
- `/api/dashboard/links/*`
- `/api/dashboard/stats`
- `/api/dashboard/analytics`
- `/api/visit/is_secured`
- `/api/visits/verify`