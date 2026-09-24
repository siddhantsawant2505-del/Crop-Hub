import os
import numpy as np
import tensorflow as tf
from sklearn.preprocessing import StandardScaler
import joblib
from skimage.feature import graycomatrix, graycoprops
import cv2

DATASET_PATH = "dataset/CyAUG-Dataset"
IMG_SIZE = (224, 224)
BATCH_SIZE = 32

def extract_glcm_features(image_array):
    img = np.array(image_array)
    img = cv2.resize(img, (224, 224))
    if img.dtype != np.uint8:
        img = (img * 255).clip(0, 255).astype(np.uint8)
    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
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

def fit_scaler():
    print("Loading dataset...")
    train_ds = tf.keras.preprocessing.image_dataset_from_directory(
        DATASET_PATH,
        validation_split=0.2,
        subset="training",
        seed=123,
        image_size=IMG_SIZE,
        batch_size=BATCH_SIZE,
    )
    
    all_textures = []
    print("Extracting features (subset) to fit scaler...")
    # We only need enough samples to get a decent mean/std
    count = 0
    max_count = 500 
    for batch_images, _ in train_ds:
        imgs = batch_images.numpy()
        for img in imgs:
            all_textures.append(extract_glcm_features(img))
            count += 1
        if count >= max_count:
            break
            
    print(f"Fitting scaler on {len(all_textures)} samples...")
    scaler = StandardScaler()
    scaler.fit(np.array(all_textures))
    
    joblib.dump(scaler, "scaler.pkl")
    print("✅ New scaler.pkl (4 features) saved!")

if __name__ == "__main__":
    if os.path.exists(DATASET_PATH):
        fit_scaler()
    else:
        print(f"Dataset not found at {DATASET_PATH}")
