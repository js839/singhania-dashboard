# Singhania Motors Dashboard

React frontend + Python backend dashboard for Supabase data.

## Run in VS Code

1. Open this folder in VS Code:
   `outputs/singhania-react-vscode`

2. Install frontend dependencies:
   ```bash
   npm install
   ```

3. Install backend dependency:
   ```bash
   python3 -m pip install psycopg2-binary
   ```

4. Start backend in one terminal:
   ```bash
   python3 server.py
   ```
   It will ask for the Supabase DB password.

5. Start React in another terminal:
   ```bash
   npm run dev
   ```

6. Open:
   `http://127.0.0.1:5173`

## Login

User email and password are validated from the Supabase `User Access` table.

## Files

- `src/App.jsx` - React dashboard logic
- `src/styles.css` - full UI styling
- `server.py` - local API backend connected to Supabase
- `public/assets/` - brand logos

## Optional API URL

By default React calls:
`http://127.0.0.1:8787`

To change it, create `.env`:
```bash
VITE_API_BASE=http://127.0.0.1:8787
```
