"""
Biblical Quotation Detector API

FastAPI application for detecting biblical quotations in Greek texts.
"""

import os
import logging
import sqlite3
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

from src.api import __version__
from src.api.models import HealthResponse, ErrorResponse
from src.api.routes import detection, verses

load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Paths
PROJECT_ROOT = Path(__file__).parent.parent.parent
DATABASE_PATH = os.getenv("DATABASE_PATH", str(PROJECT_ROOT / "data" / "processed" / "bible.db"))
QDRANT_PATH = str(PROJECT_ROOT / "data" / "processed" / "qdrant_direct")


def check_database_connection() -> bool:
    """Check if database is accessible."""
    try:
        if not Path(DATABASE_PATH).exists():
            return False
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM verses")
        conn.close()
        return True
    except Exception:
        return False


def check_vector_store_connection() -> bool:
    """Check if vector store is accessible."""
    try:
        if not Path(QDRANT_PATH).exists():
            return False
        from qdrant_client import QdrantClient
        client = QdrantClient(path=QDRANT_PATH)
        info = client.get_collection("biblical_verses")
        return info.points_count > 0
    except Exception:
        return False


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    logger.info("Starting Biblical Quotation Detector API...")
    logger.info(f"Database path: {DATABASE_PATH}")
    logger.info(f"Vector store path: {QDRANT_PATH}")

    # Check connections on startup
    db_ok = check_database_connection()
    vector_ok = check_vector_store_connection()

    if db_ok:
        logger.info("Database connection: OK")
    else:
        logger.warning("Database connection: FAILED")

    if vector_ok:
        logger.info("Vector store connection: OK")
    else:
        logger.warning("Vector store connection: FAILED")

    yield

    logger.info("Shutting down Biblical Quotation Detector API...")


# Create FastAPI app
app = FastAPI(
    title="Biblical Quotation Detector API",
    description="""
    An LLM-powered RAG agent for detecting biblical quotations in Koine Greek texts.

    ## Features

    - **Quotation Detection**: Identify biblical quotations in Greek texts
    - **Match Classification**: Exact quotes, paraphrases, allusions
    - **Confidence Scoring**: 0-100% confidence assessment
    - **Semantic Search**: Find similar biblical passages
    - **Verse Lookup**: Retrieve specific verses by reference

    ## Usage

    Send Greek text to the `/api/v1/detect` endpoint to analyze it for biblical quotations.
    """,
    version=__version__,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Exception handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": "HTTPException",
            "message": exc.detail,
            "detail": None,
        },
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle unexpected exceptions."""
    logger.error(f"Unexpected error: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "InternalServerError",
            "message": "An unexpected error occurred",
            "detail": str(exc) if os.getenv("DEBUG") else None,
        },
    )


# Health check endpoint
@app.get(
    "/health",
    response_model=HealthResponse,
    tags=["Health"],
    summary="Health check",
    description="Check the health status of the API and its dependencies.",
)
async def health_check():
    """Check API health status."""
    db_connected = check_database_connection()
    vector_connected = check_vector_store_connection()

    status = "healthy" if (db_connected and vector_connected) else "degraded"

    return HealthResponse(
        status=status,
        version=__version__,
        database_connected=db_connected,
        vector_store_connected=vector_connected,
    )


# Root endpoint
@app.get(
    "/",
    response_class=HTMLResponse,
    tags=["Root"],
    summary="API welcome page",
    include_in_schema=False,
)
async def root():
    """Serve the welcome page."""
    html_content = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Biblical Quotation Detector API</title>
        <style>
            * { box-sizing: border-box; margin: 0; padding: 0; }
            body {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
                min-height: 100vh;
                display: flex;
                justify-content: center;
                align-items: center;
                padding: 20px;
                color: #e0e0e0;
            }
            .container {
                max-width: 800px;
                background: rgba(255,255,255,0.05);
                border-radius: 16px;
                padding: 40px;
                backdrop-filter: blur(10px);
                border: 1px solid rgba(255,255,255,0.1);
            }
            h1 {
                font-size: 2.5rem;
                margin-bottom: 10px;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                background-clip: text;
            }
            .subtitle {
                color: #888;
                margin-bottom: 30px;
                font-size: 1.1rem;
            }
            .version {
                display: inline-block;
                background: rgba(102, 126, 234, 0.2);
                padding: 4px 12px;
                border-radius: 20px;
                font-size: 0.85rem;
                color: #667eea;
                margin-bottom: 20px;
            }
            .endpoints {
                margin: 30px 0;
            }
            .endpoint {
                background: rgba(255,255,255,0.03);
                border-radius: 8px;
                padding: 15px 20px;
                margin-bottom: 10px;
                display: flex;
                align-items: center;
                gap: 15px;
            }
            .method {
                font-weight: 600;
                padding: 4px 10px;
                border-radius: 4px;
                font-size: 0.8rem;
                min-width: 60px;
                text-align: center;
            }
            .method.post { background: #2d5a27; color: #7ee787; }
            .method.get { background: #1f4a6e; color: #58a6ff; }
            .path { font-family: monospace; color: #e0e0e0; }
            .desc { color: #888; font-size: 0.9rem; margin-left: auto; }
            .links {
                display: flex;
                gap: 15px;
                margin-top: 30px;
            }
            .links a {
                display: inline-block;
                padding: 12px 24px;
                border-radius: 8px;
                text-decoration: none;
                font-weight: 500;
                transition: all 0.2s;
            }
            .links a.primary {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
            }
            .links a.secondary {
                background: rgba(255,255,255,0.1);
                color: #e0e0e0;
            }
            .links a:hover { transform: translateY(-2px); }
            .greek { font-style: italic; color: #888; }
        </style>
    </head>
    <body>
        <div class="container">
            <span class="version">v""" + __version__ + """</span>
            <h1>Biblical Quotation Detector</h1>
            <p class="subtitle">LLM-powered RAG agent for detecting biblical quotations in Koine Greek texts</p>

            <div class="endpoints">
                <div class="endpoint">
                    <span class="method post">POST</span>
                    <span class="path">/api/v1/detect</span>
                    <span class="desc">Detect biblical quotations</span>
                </div>
                <div class="endpoint">
                    <span class="method post">POST</span>
                    <span class="path">/api/v1/detect/batch</span>
                    <span class="desc">Batch detection</span>
                </div>
                <div class="endpoint">
                    <span class="method post">POST</span>
                    <span class="path">/api/v1/search</span>
                    <span class="desc">Semantic search</span>
                </div>
                <div class="endpoint">
                    <span class="method get">GET</span>
                    <span class="path">/api/v1/verse/{reference}</span>
                    <span class="desc">Get verse by reference</span>
                </div>
                <div class="endpoint">
                    <span class="method get">GET</span>
                    <span class="path">/health</span>
                    <span class="desc">Health check</span>
                </div>
            </div>

            <p class="greek">Example: "Μακάριοι οἱ πτωχοὶ τῷ πνεύματι" (Matthew 5:3)</p>

            <div class="links">
                <a href="/docs" class="primary">API Documentation</a>
                <a href="/redoc" class="secondary">ReDoc</a>
                <a href="/app" class="secondary">Try It</a>
            </div>
        </div>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)


# Web application interface
@app.get(
    "/app",
    response_class=HTMLResponse,
    tags=["App"],
    summary="Interactive web interface",
    include_in_schema=False,
)
async def web_app():
    """Serve the interactive web application."""
    html_content = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Biblical Quotation Detector</title>
        <style>
            * { box-sizing: border-box; margin: 0; padding: 0; }
            body {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
                min-height: 100vh;
                padding: 20px;
                color: #e0e0e0;
            }
            .container {
                max-width: 900px;
                margin: 0 auto;
            }
            header {
                text-align: center;
                margin-bottom: 30px;
            }
            h1 {
                font-size: 2rem;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                background-clip: text;
                margin-bottom: 5px;
            }
            .subtitle { color: #888; font-size: 0.95rem; }
            .card {
                background: rgba(255,255,255,0.05);
                border-radius: 12px;
                padding: 25px;
                margin-bottom: 20px;
                border: 1px solid rgba(255,255,255,0.1);
            }
            .card h2 {
                font-size: 1.1rem;
                margin-bottom: 15px;
                color: #667eea;
            }
            textarea {
                width: 100%;
                min-height: 120px;
                padding: 15px;
                border-radius: 8px;
                border: 1px solid rgba(255,255,255,0.2);
                background: rgba(0,0,0,0.3);
                color: #e0e0e0;
                font-size: 1.1rem;
                font-family: 'Times New Roman', serif;
                resize: vertical;
            }
            textarea:focus {
                outline: none;
                border-color: #667eea;
            }
            textarea::placeholder { color: #666; }
            .controls {
                display: flex;
                gap: 15px;
                margin-top: 15px;
                flex-wrap: wrap;
                align-items: center;
            }
            .control-group {
                display: flex;
                align-items: center;
                gap: 8px;
            }
            .control-group label {
                font-size: 0.85rem;
                color: #888;
            }
            select {
                padding: 8px 12px;
                border-radius: 6px;
                border: 1px solid rgba(255,255,255,0.2);
                background: rgba(0,0,0,0.3);
                color: #e0e0e0;
                font-size: 0.9rem;
            }
            button {
                padding: 12px 28px;
                border-radius: 8px;
                border: none;
                font-weight: 600;
                cursor: pointer;
                transition: all 0.2s;
            }
            button.primary {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
            }
            button.secondary {
                background: rgba(255,255,255,0.1);
                color: #e0e0e0;
            }
            button:hover { transform: translateY(-2px); }
            button:disabled {
                opacity: 0.5;
                cursor: not-allowed;
                transform: none;
            }
            .examples {
                display: flex;
                gap: 10px;
                flex-wrap: wrap;
                margin-top: 10px;
            }
            .example-btn {
                padding: 6px 12px;
                font-size: 0.8rem;
                background: rgba(102, 126, 234, 0.2);
                color: #667eea;
                border: 1px solid rgba(102, 126, 234, 0.3);
            }
            #result {
                display: none;
            }
            #result.show { display: block; }
            .result-header {
                display: flex;
                align-items: center;
                gap: 15px;
                margin-bottom: 20px;
            }
            .status-badge {
                padding: 6px 16px;
                border-radius: 20px;
                font-weight: 600;
                font-size: 0.85rem;
            }
            .status-badge.quotation {
                background: rgba(46, 160, 67, 0.2);
                color: #7ee787;
            }
            .status-badge.not-quotation {
                background: rgba(248, 81, 73, 0.2);
                color: #f85149;
            }
            .confidence {
                font-size: 1.5rem;
                font-weight: 700;
                color: #667eea;
            }
            .match-type {
                padding: 4px 12px;
                background: rgba(255,255,255,0.1);
                border-radius: 4px;
                font-size: 0.85rem;
            }
            .explanation {
                background: rgba(0,0,0,0.2);
                padding: 15px;
                border-radius: 8px;
                margin-bottom: 20px;
                line-height: 1.6;
            }
            .source-card {
                background: rgba(0,0,0,0.2);
                border-radius: 8px;
                padding: 15px;
                margin-bottom: 10px;
                border-left: 3px solid #667eea;
            }
            .source-ref {
                font-weight: 600;
                color: #667eea;
                margin-bottom: 8px;
            }
            .source-text {
                font-family: 'Times New Roman', serif;
                font-size: 1.1rem;
                color: #e0e0e0;
                margin-bottom: 8px;
            }
            .source-score {
                font-size: 0.85rem;
                color: #888;
            }
            .processing-time {
                text-align: right;
                font-size: 0.85rem;
                color: #666;
                margin-top: 15px;
            }
            .loading {
                text-align: center;
                padding: 40px;
            }
            .spinner {
                width: 40px;
                height: 40px;
                border: 3px solid rgba(102, 126, 234, 0.3);
                border-top-color: #667eea;
                border-radius: 50%;
                animation: spin 1s linear infinite;
                margin: 0 auto 15px;
            }
            @keyframes spin {
                to { transform: rotate(360deg); }
            }
            .error {
                background: rgba(248, 81, 73, 0.1);
                border: 1px solid rgba(248, 81, 73, 0.3);
                color: #f85149;
                padding: 15px;
                border-radius: 8px;
            }
            .back-link {
                display: inline-block;
                color: #667eea;
                text-decoration: none;
                margin-bottom: 20px;
                font-size: 0.9rem;
            }
            .back-link:hover { text-decoration: underline; }
        </style>
    </head>
    <body>
        <div class="container">
            <a href="/" class="back-link">&larr; Back to API</a>

            <header>
                <h1>Biblical Quotation Detector</h1>
                <p class="subtitle">Detect biblical quotations in Koine Greek texts</p>
            </header>

            <div class="card">
                <h2>Enter Greek Text</h2>
                <textarea id="input" placeholder="Enter Greek text to analyze..."></textarea>

                <div class="examples">
                    <button class="example-btn" onclick="setExample(0)">Beatitudes</button>
                    <button class="example-btn" onclick="setExample(1)">John 1:1</button>
                    <button class="example-btn" onclick="setExample(2)">John 3:16</button>
                    <button class="example-btn" onclick="setExample(3)">Lord's Prayer</button>
                    <button class="example-btn" onclick="setExample(4)">Non-biblical</button>
                </div>

                <div class="controls">
                    <div class="control-group">
                        <label>Mode:</label>
                        <select id="mode">
                            <option value="llm">LLM (Accurate)</option>
                            <option value="heuristic">Heuristic (Fast)</option>
                        </select>
                    </div>
                    <div class="control-group">
                        <label>Min Confidence:</label>
                        <select id="confidence">
                            <option value="50">50%</option>
                            <option value="70">70%</option>
                            <option value="80">80%</option>
                            <option value="90">90%</option>
                        </select>
                    </div>
                    <button class="primary" id="detectBtn" onclick="detect()">Detect Quotation</button>
                </div>
            </div>

            <div class="card" id="result">
                <div id="resultContent"></div>
            </div>
        </div>

        <script>
            const examples = [
                "Μακάριοι οἱ πτωχοὶ τῷ πνεύματι",
                "Ἐν ἀρχῇ ἦν ὁ λόγος",
                "οὕτως γὰρ ἠγάπησεν ὁ θεὸς τὸν κόσμον",
                "Πάτερ ἡμῶν ὁ ἐν τοῖς οὐρανοῖς",
                "Ὁ φιλόσοφος ἐν τῇ ἀγορᾷ διδάσκει τοὺς νέους"
            ];

            function setExample(index) {
                document.getElementById('input').value = examples[index];
            }

            async function detect() {
                const input = document.getElementById('input').value.trim();
                if (!input) {
                    alert('Please enter some Greek text');
                    return;
                }

                const mode = document.getElementById('mode').value;
                const confidence = parseInt(document.getElementById('confidence').value);
                const resultDiv = document.getElementById('result');
                const resultContent = document.getElementById('resultContent');
                const detectBtn = document.getElementById('detectBtn');

                detectBtn.disabled = true;
                resultDiv.classList.add('show');
                resultContent.innerHTML = `
                    <div class="loading">
                        <div class="spinner"></div>
                        <p>Analyzing text...</p>
                    </div>
                `;

                try {
                    const response = await fetch('/api/v1/detect', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            text: input,
                            mode: mode,
                            min_confidence: confidence,
                            include_all_candidates: false
                        })
                    });

                    const data = await response.json();

                    if (!response.ok) {
                        throw new Error(data.message || 'Detection failed');
                    }

                    renderResult(data);
                } catch (error) {
                    resultContent.innerHTML = `
                        <div class="error">
                            <strong>Error:</strong> ${error.message}
                        </div>
                    `;
                } finally {
                    detectBtn.disabled = false;
                }
            }

            function renderResult(data) {
                const resultContent = document.getElementById('resultContent');

                const statusClass = data.is_quotation ? 'quotation' : 'not-quotation';
                const statusText = data.is_quotation ? 'Biblical Quotation' : 'Not a Quotation';

                let sourcesHtml = '';
                if (data.sources && data.sources.length > 0) {
                    sourcesHtml = '<h3 style="margin: 20px 0 10px; font-size: 1rem;">Matching Sources</h3>';
                    for (const source of data.sources) {
                        sourcesHtml += `
                            <div class="source-card">
                                <div class="source-ref">${source.reference}</div>
                                <div class="source-text">${source.greek_text}</div>
                                <div class="source-score">Similarity: ${(source.similarity_score * 100).toFixed(1)}%</div>
                            </div>
                        `;
                    }
                }

                resultContent.innerHTML = `
                    <div class="result-header">
                        <span class="status-badge ${statusClass}">${statusText}</span>
                        <span class="confidence">${data.confidence}%</span>
                        <span class="match-type">${data.match_type.replace('_', ' ')}</span>
                    </div>

                    <div class="explanation">${data.explanation}</div>

                    ${sourcesHtml}

                    <div class="processing-time">Processed in ${data.processing_time_ms}ms</div>
                `;
            }
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)


# Include routers
app.include_router(detection.router, prefix="/api/v1", tags=["Detection"])
app.include_router(verses.router, prefix="/api/v1", tags=["Verses"])


# Run with: uvicorn src.api.main:app --reload
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "src.api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
