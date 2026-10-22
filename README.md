# Rarh Weather App

Weather forecasting and agricultural advisory web app for the Rarh region, with a frontend and Flask/Python backend.

## Application source

The app source archive is `rarh-weather-app-github-ready.zip`, prepared separately. **The source files still need to be added to this repository.** Extract the ZIP and upload its contents to the repository root (not the ZIP itself). Keep the `.github/workflows/pages.yml` directory, `frontend/`, `backend/`, and `render.yaml`.

## Frontend: GitHub Pages

Once the project files are uploaded, open **Settings > Pages** and set the source to **GitHub Actions**. The included workflow will publish the static frontend at https://Shubha-fm.github.io/rarh-weather-app/ .

## Backend: Render

Use the repository's `render.yaml` with Render's **New > Blueprint** deployment. After deploying, set the backend URL in `frontend/js/config.js` to your Render service URL, and commit the change. Verify CORS, the app's API endpoints, secrets, and persistent storage before using real farmer accounts.

## Local development

Follow the backend requirements in `backend/requirements.txt` and run the Flask entrypoint in `backend/run.py`. The frontend is in `frontend/`.

**Deployment status:** Repository initialized; app code upload and hosting configuration pending.
