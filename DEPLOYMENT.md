# Singhania Motors Dashboard Deployment

## What To Deploy

This project can run on Vercel as one app:

- React frontend is built with Vite.
- `/api/login` and `/api/report` run as Vercel Python serverless functions.
- The same `server.py` still works for local development.

## Environment Variables

Vercel:

```bash
SUPABASE_DB_PASSWORD=your-supabase-db-password
SESSION_SECRET=any-long-random-secret
```

Leave `VITE_API_BASE` empty on Vercel. The frontend will call same-domain `/api/login` and `/api/report`.

## Vercel Steps

1. Push the contents of this folder to GitHub.
2. In Vercel, import the GitHub repo.
3. Set framework to `Vite`.
4. Build command: `npm run build`.
5. Output directory: `dist`.
6. Add `SUPABASE_DB_PASSWORD` and `SESSION_SECRET` in Vercel Environment Variables.
7. Make sure the Vercel project root is the folder that contains `package.json`.
8. Deploy.

## If Your GitHub Repo Has This Folder Inside Another Folder

Set Vercel Project Settings -> Root Directory to:

```bash
outputs/singhania-react-vscode
```

If the GitHub repo already contains the files directly at root, leave Root Directory blank.

## Local Development

```bash
npm install
python3 -m pip install psycopg2-binary
python3 server.py
npm run dev
```

## Real-Time Data

The dashboard reads Supabase fresh on every report request. Once hosted, users will see current database data without running anything locally.
