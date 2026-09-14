export const environment = {
  production: true,
  // For Docker deployment, use the hostname. When running in Docker:
  // - Frontend runs at http://localhost:4200 (nginx on port 80)
  // - Backend runs at http://localhost:8000 (FastAPI backend)
  // The browser will resolve this from the host machine.
  apiUrl: 'http://localhost:8000/api',
};
