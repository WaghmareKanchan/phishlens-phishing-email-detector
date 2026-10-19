// Same origin by default (FastAPI serves this page). To host the HTML elsewhere, set
// window.PHISHLENS_API_BASE = "https://api.example.com/api" in a <script> before app.js
// and add your page's origin to CORS_ORIGINS in backend/.env.
export const API_BASE = (window.PHISHLENS_API_BASE || '/api').replace(/\/$/, '');
