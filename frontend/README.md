# Scholar Frontend

React, TypeScript, and Vite client for the Academic QA service. The frontend reads the shared root `.env` through `vite.config.js`.

```sh
npm install
npm run dev
```

Set `VITE_API_BASE_URL=http://localhost:8000/api` and `VITE_USE_MOCKS=false` to use the FastAPI backend. For Vercel, set this project's Root Directory to `frontend` and configure `VITE_API_BASE_URL` to the backend deployment URL. See `../backend/README.md` for API deployment setup.
