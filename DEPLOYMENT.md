# Singhania Motors Dashboard Deployment

## What To Deploy

This project has two parts:

- React frontend: deploy this folder to Vercel.
- Python backend: deploy `server.py` to a Python hosting service such as Render, Railway, Fly.io, or a VPS.

Vercel is excellent for the React frontend. The current backend is a long-running Python HTTP server, so it should run on a backend host unless it is converted to Vercel serverless functions.

## Environment Variables

Backend host:

```bash
SUPABASE_DB_PASSWORD=your-supabase-db-password
```

Frontend/Vercel:

```bash
VITE_API_BASE=https://your-backend-domain.example.com
```

## Vercel Frontend Steps

1. Push `outputs/singhania-react-vscode` to GitHub.
2. In Vercel, import the GitHub repo.
3. Set framework to `Vite`.
4. Build command: `npm run build`.
5. Output directory: `dist`.
6. Add `VITE_API_BASE` in Vercel Environment Variables.
7. Deploy.

## Backend Steps

1. Upload this same project or at least `server.py` plus required Python dependencies to a backend host.
2. Install Python dependency:

```bash
pip install psycopg2-binary
```

3. Set `SUPABASE_DB_PASSWORD` as a secret environment variable.
4. Start command:

```bash
python server.py
```

5. Use the backend public URL as `VITE_API_BASE` in Vercel.

## Real-Time Data

The dashboard reads Supabase fresh on every report request. Once hosted, users will see current database data without running anything locally.
