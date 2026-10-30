from flask import Flask, render_template, request, jsonify
from scraper import get_cs_jobs
import time

app = Flask(__name__)

# Simple in-memory cache so we don't scrape target websites on every single request
CACHE = {
    "jobs": [],
    "last_updated": 0
}
CACHE_TIMEOUT = 600  # Refresh cache every 10 minutes (600 seconds)

def get_cached_jobs(force_refresh=False):
    now = time.time()
    if force_refresh or not CACHE["jobs"] or (now - CACHE["last_updated"] > CACHE_TIMEOUT):
        CACHE["jobs"] = get_cs_jobs()
        CACHE["last_updated"] = now
    return CACHE["jobs"]

@app.route("/")
def index():
    query = request.args.get("query", "").strip().lower()
    category = request.args.get("category", "").strip()
    
    jobs = get_cached_jobs()
    
    # Filter by search query
    if query:
        jobs = [
            j for j in jobs 
            if query in j["title"].lower() 
            or query in j["snippet"].lower() 
            or query in j["company"].lower()
        ]
        
    # Filter by category
    if category and category != "All":
        jobs = [j for j in jobs if j["category"] == category]
        
    categories = ["All", "Software Development", "IT Operations & Support", "Networks & Systems", "Data & Analytics", "General CS/IT"]
    
    return render_template(
        "index.html", 
        jobs=jobs, 
        total_jobs=len(jobs), 
        query=query, 
        selected_category=category,
        categories=categories
    )

@app.route("/api/refresh", methods=["POST"])
def refresh():
    """Endpoint to trigger a fresh web scrape."""
    get_cached_jobs(force_refresh=True)
    return jsonify({"status": "success", "message": "Jobs database refreshed!"})

if __name__ == "__main__":
    app.run(debug=True, port=5000)