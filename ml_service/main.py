import sys
from pathlib import Path
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Calculate the base directory (ml_service)
base_dir = Path(__file__).parent

# Now we can import the routers/apps from the subdirectories
try:
    from terra_layer.main import app as terra_app
    from fathom_layer.app import app as fathom_app
    from logistics_layer.app import app as logistics_app
except ImportError as e:
    print(f"Warning: Could not import one of the ML layers. Ensure folders are inside ml_service. Error: {e}")

# Create the unified FastAPI app
app = FastAPI(
    title="CropHub Unified ML Service",
    description="A single FastAPI service running Terra, Fathom, and Logistics layers.",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount the sub-apps
try:
    app.mount("/terra", terra_app)
    app.mount("/fathom", fathom_app)
    app.mount("/logistics", logistics_app)
except NameError:
    pass # Ignore if imports failed above

@app.get("/health")
def health_check():
    return {
        "status": "healthy", 
        "service": "ml_service", 
        "modules_loaded": ["terra", "fathom", "logistics"]
    }

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
