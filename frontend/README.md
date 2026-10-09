# Frontend (Next.js)

The dashboard UI. For full setup, including the backend and database, see the
[root README](../README.md).

```powershell
npm install
npm run dev         # http://localhost:3000 (expects the backend on http://127.0.0.1:8000)
npm test            # Vitest + React Testing Library
npm run lint        # ESLint
npm run typecheck   # next typegen + tsc
npm run build       # production build
```

`/api/*` is proxied to `BACKEND_URL` (default `http://127.0.0.1:8000`). To override it, put
`BACKEND_URL` in `frontend/.env.local`.
