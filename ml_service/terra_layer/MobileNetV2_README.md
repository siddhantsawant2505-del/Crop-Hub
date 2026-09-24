# MobileNetV2 Soil Analysis Engine 📂🌱

This document explains the integration and technical implementation of the **MobileNetV2** architecture within the **CropHub** ecosystem, specifically powering the **Terra Layer** (Soil Intelligence Service).

---

## 🏗️ Model Architecture

We leverage **MobileNetV2**, a streamlined and efficient convolutional neural network, as the backbone for our soil classification system. It is specifically chosen for its high performance on mobile and edge devices, ensuring our backend remains fast and scalable.

### 1. The Backbone
- **Base Model**: `tf.keras.applications.MobileNetV2`
- **Pre-trained Weights**: `ImageNet` (Transfer Learning)
- **Input Resolution**: `224x224x3` (RGB)
- **Feature Extraction**: Depthwise separable convolutions help minimize computational load while maintaining high accuracy in extracting texture and color patterns from soil images.

### 2. Custom Classification Head
The top layers of the original MobileNetV2 are replaced with a custom head tailored for agricultural soil types:
- **GlobalAveragePooling2D**: Reduces the spatial dimensions of the feature maps.
- **Dense Layer (128 units)**: A fully connected layer with `ReLU` activation for non-linear feature mapping.
- **Output Layer**: A `Softmax` activated layer corresponding to our target soil classes.

---

## 🧪 Training Process

The model is trained to recognize specific soil profiles essential for agricultural decision-making.

| Phase | Description |
| :--- | :--- |
| **Dataset** | Trained on the **CyAUG-Dataset**, containing high-resolution images of various soil types. |
| **Preprocessing** | Images are resized to 224x224 and pixel values are scaled to a `[-1, 1]` range using internal model rescaling layers. |
| **Transfer Learning** | The base MobileNetV2 weights are initially **frozen** to preserve ImageNet feature extraction, while the custom head learns soil-specific features. |
| **Optimization** | Utilizes the `Adam` optimizer with `SparseCategoricalCrossentropy` loss for efficient convergence. |

---

## 🔍 How it Works in Our System

The `TerraAnalyzer` class (located in `analyzer.py`) orchestrates the inference pipeline:

### 1. Validation Logic
Before classification, the system performs rigorous checks:
- **Format Check**: Only high-quality JPEGs, PNGs, etc., are accepted.
- **Resolution Check**: Minimum 100x100 resolution required.
- **Corruption Check**: PIL conversion ensures the file isn't truncated.

### 2. Inference & Confidence Handling
> [!IMPORTANT]
> **Confidence Threshold: 65%**
> To prevent "Garbage In, Garbage Out," any image that scores below 65% confidence is rejected. This ensures that the user doesn't accidentally receive a soil report for a photo of a dog or a tractor.

### 3. Detected Soil Classes
The system identifies the following soil types:
*   `Alluvial Soil`
*   `Arid Soil`
*   `Black Soil`
*   `Laterite Soil`
*   `Mountain Soil`
*   `Red Soil`
*   `Yellow Soil`

---

## 🌐 Holistic Integration (The "Terra Layer")

MobileNetV2 doesn't work in isolation. Its predictions are cross-referenced with external data to provide a "Sovereign Intelligence" report:

1.  **Visual Prediction**: MobileNetV2 identifies the soil from the photo.
2.  **Geospatial Verification**: The system queries **ISRIC SoilGrids** using the user's GPS coordinates to see what soil is *expected* in that region.
3.  **Weather Context**: Real-time data from **Open-Meteo** (temperature and precipitation) is pulled to assess current moisture levels.
4.  **Final Report**: The system generates a comprehensive PDF/UI report including:
    *   Soil Health Status (Optimal, Moderate, or Deficient)
    *   Workability Window
    *   Crop Recommendations (Ideal crops vs. Warning crops)

---

## 🛠️ Usage for Developers

To retrain the model with fresh data:
```bash
python terra_layer/train_model.py
```

To run inference via the API:
```python
from terra_layer.analyzer import TerraAnalyzer
analyzer = TerraAnalyzer()
report = analyzer.generate_report(lat, lon, survey_data, image_bytes)
```

---
*Developed by the CropHub Engineering Team*
