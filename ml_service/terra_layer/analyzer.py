import os
import io
import cv2
import logging
import requests
import numpy as np
from PIL import Image
from PIL import UnidentifiedImageError
from skimage.feature import graycomatrix, graycoprops
import joblib

import time
from concurrent.futures import ThreadPoolExecutor
try:
    from tensorflow.keras.models import load_model
except ImportError:
    load_model = None

logger = logging.getLogger(__name__)


def extract_glcm_features(image_array):
    """
    Extract 4 GLCM texture features from a BGR image array.
    Matches the feature vector used during training.
    Returns numpy array of shape (4,).
    """
    img = cv2.resize(image_array, (224, 224))
    if img.dtype != np.uint8:
        img = (img * 255).astype(np.uint8)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    glcm = graycomatrix(
        gray, distances=[1, 3], angles=[0, 45, 90],
        levels=256, symmetric=True, normed=True
    )
    features = np.array([
        graycoprops(glcm, 'contrast').mean(),
        graycoprops(glcm, 'homogeneity').mean(),
        graycoprops(glcm, 'energy').mean(),
        graycoprops(glcm, 'correlation').mean(),
    ])
    return features


class TerraAnalyzer:
    def __init__(self, model_path=None):
        if model_path is None:
            self.model_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "model.keras")
        else:
            self.model_path = model_path
        self.soil_classes = [
            'Alluvial_Soil', 'Arid_Soil', 'Black_Soil',
            'Laterite_Soil', 'Mountain_Soil', 'Red_Soil', 'Yellow_Soil'
        ]

        self.model = None
        self.scaler = None

        if load_model and os.path.exists(self.model_path):
            try:
                self.model = load_model(self.model_path)
                logger.info("Model loaded successfully")
            except Exception as e:
                logger.error(f"Model load error: {e}")
        else:
            logger.warning("Model file not found or Keras not available")

        # Load the persisted StandardScaler produced by train_model.py
        scaler_path = os.path.join(os.path.dirname(self.model_path) or ".", "scaler.pkl")
        if os.path.exists(scaler_path):
            try:
                self.scaler = joblib.load(scaler_path)
                logger.info("Texture scaler loaded successfully")
            except Exception as e:
                logger.error(f"Scaler load error: {e}")
        else:
            logger.warning(
                f"scaler.pkl not found at '{scaler_path}'. "
                "Run train_model.py first to generate it. Texture features will be unscaled."
            )

    # ---------------- FILE VALIDATION ----------------
    def validate_image_file(self, image_bytes, max_size_mb=10):
        """
        Validate image file before processing.
        """
        file_size_mb = len(image_bytes) / (1024 * 1024)
        if file_size_mb > max_size_mb:
            raise ValueError(f"Image too large: {file_size_mb:.1f}MB (max {max_size_mb}MB)")
        
        if file_size_mb < 0.01:
            raise ValueError("Image too small (minimum 10KB)")
        
        try:
            img = Image.open(io.BytesIO(image_bytes))
            
            allowed_formats = {'JPEG', 'PNG', 'BMP', 'GIF', 'WEBP'}
            if img.format not in allowed_formats:
                raise ValueError(f"Unsupported image format: {img.format}")
            
            width, height = img.size
            if width < 100 or height < 100:
                raise ValueError(f"Image too small ({width}x{height}). Min 100x100 required.")
            
            # Catch potential corrupted files
            img.convert('RGB')
            return True
            
        except UnidentifiedImageError:
            raise ValueError("File is not a valid image")
        except Exception as e:
            raise ValueError(f"Invalid image file: {str(e)}")

    # ---------------- WEATHER ----------------
    def fetch_weather_data(self, lat, lon):
        try:
            url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,precipitation"
            res = requests.get(url, timeout=10).json()
            return {
                "temp_c": res["current"]["temperature_2m"],
                "rain_mm": res["current"]["precipitation"]
            }
        except Exception:
            return {"temp_c": 25, "rain_mm": 0}

    # ---------------- IMAGE ANALYSIS ----------------
    def analyze_image_opencv(self, image_bytes, confidence_threshold=0.65):
        """
        Analyze image and return soil classification.
        """
        image = Image.open(io.BytesIO(image_bytes)).convert('RGB')
        img_np = np.array(image)
        img_bgr = img_np[:, :, ::-1].copy()

        hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
        avg_hsv = np.mean(hsv, axis=(0, 1))
        graininess = cv2.Laplacian(img_bgr, cv2.CV_64F).var()

        predicted = "Unknown"
        confidence = 0.0

        if self.model:
            # ── Prepare image input (RGB, [0,255]) ──
            resized = cv2.resize(img_np, (224, 224))
            img_arr = np.expand_dims(resized.astype(np.uint8), axis=0)

            # ── Prepare texture input (4 GLCM features, scaled) ──
            # Feature order: [contrast, homogeneity, energy, correlation]
            raw_texture = extract_glcm_features(img_bgr).reshape(1, -1)  # shape (1, 4)

            if self.scaler is not None:
                # Use the training scaler — guarantees identical mean/std as during training
                texture_scaled = self.scaler.transform(raw_texture)
            else:
                # Fallback: pass raw unscaled features (accuracy will be degraded)
                logger.warning("scaler.pkl not loaded — using unscaled texture features.")
                texture_scaled = raw_texture

            # ── Dual-input prediction ──
            logger.info(f"DEBUG: img_arr shape={img_arr.shape}, texture_scaled shape={texture_scaled.shape}")
            preds = self.model.predict([img_arr, texture_scaled], verbose=0)[0]

            confidence = float(np.max(preds))
            pred_idx = int(np.argmax(preds))

            # CRITICAL: Validate it's actually soil
            if confidence < confidence_threshold:
                raise ValueError(
                    f"Image is not clearly a soil image. "
                    f"Confidence: {confidence:.1%} (min required: {confidence_threshold:.0%}). "
                    f"Please upload a clear, close-up image of actual soil."
                )

            predicted = self.soil_classes[pred_idx]
        else:
            logger.warning("No model available - analysis rejected")
            raise ValueError("Soil prediction model not loaded. Analysis unavailable.")

        return {
            "hsv": avg_hsv,
            "graininess": graininess,
            "soil_type": predicted,
            "model_confidence": confidence
        }

    # ---------------- GEOGRAPHIC SOIL DB ----------------
    def get_regional_soil_profile(self, lat, lon):
        try:
            url = "https://rest.isric.org/soilgrids/v2.0/properties/query"
            params = {
                'lon': lon, 'lat': lat,
                'property': ['clay', 'sand', 'silt', 'ph', 'nitrogen'],
                'depth': '0-5cm'
            }
            response = requests.get(url, params=params, timeout=10).json()
            if 'properties' not in response:
                return None
            
            props = response['properties']
            return {
                'clay_percent': props.get('clay', {}).get('0-5cm_mean', 0) / 10,
                'sand_percent': props.get('sand', {}).get('0-5cm_mean', 0) / 10,
                'silt_percent': props.get('silt', {}).get('0-5cm_mean', 0) / 10,
                'ph': props.get('ph', {}).get('0-5cm_mean', 65) / 10,
                'nitrogen': props.get('nitrogen', {}).get('0-5cm_mean', 0) / 100
            }
        except Exception:
            return None

    def classify_by_regional_data(self, regional_soil):
        if not regional_soil: return "Unknown"
        clay, sand, silt = regional_soil['clay_percent'], regional_soil['sand_percent'], regional_soil['silt_percent']
        if clay > 40: return "Clay_Soil"
        if sand > 70: return "Sandy_Soil"
        if clay > 27 and silt > 27: return "Loam_Soil"
        return "Mixed_Soil"

    # ---------------- MAIN REPORT ----------------
    def generate_report(self, lat, lon, survey, image_bytes=None):
        start_total = time.perf_counter()
        
        # We'll run weather and regional soil calls in parallel with image analysis
        with ThreadPoolExecutor(max_workers=3) as executor:
            # 1. Start weather fetch
            weather_task = executor.submit(self.fetch_weather_data, lat, lon)
            
            # 2. Start regional soil fetch
            regional_task = executor.submit(self.get_regional_soil_profile, lat, lon)
            
            # 3. Start image analysis (this is the heaviest task)
            image_data = {}
            if image_bytes:
                # We can run this in the main thread or another executor thread
                # Analysis itself already has internal timing logic if desired
                try:
                    image_data = self.analyze_image_opencv(image_bytes, confidence_threshold=0.65)
                except Exception as e:
                    logger.error(f"Image analysis failed: {e}")
                    raise
            
            # Wait for external APIs
            weather = weather_task.result()
            regional_soil = regional_task.result()

        t_total = time.perf_counter() - start_total
        logger.info(f"PERF: Report generated in {t_total:.3f}s")

        wetness = int(survey.get("wetness", 5))
        texture = survey.get("texture", "Unknown")
        grain = image_data.get("graininess", 300)
        soil_type = image_data.get("soil_type", "Unknown")
        confidence = image_data.get("model_confidence", 0.0)

        regional_type = self.classify_by_regional_data(regional_soil)

        # Logic
        if grain < 200 and wetness > 6:
            health = "Optimal"
        elif grain > 800:
            health = "Deficient"
        else:
            health = "Moderate"

        # Quality scoring (for Fathom Layer)
        if health == "Optimal":
            quality_score = 85.0 + (confidence * 10)
        elif health == "Moderate":
            quality_score = 65.0 + (confidence * 5)
        else:
            quality_score = 40.0 + (confidence * 5)
        quality_score = min(100.0, float(quality_score))

        # Format soil type for human-readable display ("Alluvial_Soil" -> "Alluvial Soil")
        soil_type_display = soil_type.replace('_', ' ')
        regional_type_display = regional_type.replace('_', ' ')

        interpretation = f"Soil detected as {soil_type_display} (Confidence: {confidence:.1%}). "
        if regional_type != "Unknown" and soil_type != "Unknown":
            if regional_type.split('_')[0] not in soil_type:
                interpretation += f"⚠️ Note: Regional data suggests {regional_type_display}."

        hydro = "Stable" if 3 <= wetness <= 8 else ("Flood Risk" if wetness > 8 else "Drought Risk")
        work = "Good" if 200 <= grain <= 800 else ("Clay-like" if grain < 200 else "Too Sandy")

        # Class names use underscores (e.g. "Black_Soil", "Red_Soil", "Alluvial_Soil")
        if "Black" in soil_type:
            crops = ["Cotton", "Soybean", "Wheat"]
            warning = "Rice"
        elif "Red" in soil_type or "Laterite" in soil_type:
            crops = ["Groundnut", "Millets", "Pulses"]
            warning = "Sugarcane"
        elif "Alluvial" in soil_type:
            crops = ["Rice", "Wheat", "Sugarcane", "Jute"]
            warning = "None"
        elif "Arid" in soil_type:
            crops = ["Bajra", "Jowar", "Barley"]
            warning = "Water-intensive crops"
        elif "Mountain" in soil_type:
            crops = ["Tea", "Coffee", "Spices"]
            warning = "Heavy machinery use"
        elif "Yellow" in soil_type:
            crops = ["Groundnut", "Potato", "Rice"]
            warning = "Over-irrigation"  
        else:
            crops = ["Vegetables", "Maize"]
            warning = "None"

        return {
            "health_status": health,
            "key_interpretation": interpretation,
            "hydrology_alert": hydro,
            "workability_window": work,
            "ideal_crops": crops,
            "warning_crop": warning,
            "action_plan": [
                f"Detected: {soil_type_display}",
                f"Texture Survey: {texture} | Wetness: {wetness}/10",
                f"Region Context: {regional_type_display}",
                f"Weather: {weather['temp_c']}°C",
            ],
            "soil_type_raw": soil_type,
            "soil_quality_score": round(quality_score, 1),
            "soil_type_confidence": round(confidence, 4),
            "confidence_percentage": round(confidence * 100, 2),
            "validation_status": "validated" if confidence >= 0.65 else "unvalidated"
        }