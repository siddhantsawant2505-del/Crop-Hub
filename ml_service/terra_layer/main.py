from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import json
import logging
from .analyzer import TerraAnalyzer

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Terra Layer Service")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

analyzer = TerraAnalyzer()

@app.post("/api/analyze")
async def analyze_soil(
    lat: float = Form(...),
    lon: float = Form(...),
    survey: str = Form(...),
    image: UploadFile = File(...)
):
    try:
        survey_dict = json.loads(survey)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid survey JSON format")

    # Read image bytes
    image_bytes = await image.read()
    if not image_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    try:
        # 1. Physical validation (File size, format, dimensions)
        analyzer.validate_image_file(image_bytes)
        
        # 2. Intellectual validation (CNN confidence threshold check)
        # and report generation
        report = analyzer.generate_report(
            lat=lat, 
            lon=lon, 
            survey=survey_dict, 
            image_bytes=image_bytes
        )
        
        return {
            "success": True, 
            "report": report,
            "status": "analysis_v2_active"
        }
        
    except ValueError as val_err:
        # This catches soil validation errors (e.g. non-soil image)
        logger.warning(f"Validation failed: {val_err}")
        raise HTTPException(status_code=400, detail=str(val_err))
        
    except Exception as e:
        logger.error(f"Internal processing error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "terra_layer"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
