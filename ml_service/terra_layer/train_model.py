import os
import shutil
import numpy as np
import tensorflow as tf
from tensorflow.keras.applications import MobileNetV2
from tensorflow.keras.layers import (
    Dense, GlobalAveragePooling2D, Dropout,
    Input, Concatenate
)
from tensorflow.keras.models import Model
from tensorflow.keras.callbacks import EarlyStopping, ReduceLROnPlateau

# ✅ FIX 1: These were missing — caused NameError on confusion_matrix
from sklearn.metrics import confusion_matrix, classification_report, ConfusionMatrixDisplay
from sklearn.preprocessing import StandardScaler
from sklearn.utils.class_weight import compute_class_weight
import joblib

from skimage.feature import graycomatrix, graycoprops
import cv2
import matplotlib.pyplot as plt

# ─────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────
DATASET_PATH    = "dataset/CyAUG-Dataset"
MODEL_SAVE      = "model.keras"
SPECIALIST_SAVE = "specialist_laterite_red.keras"
EVAL_DIR        = "evaluation"
IMG_SIZE        = (224, 224)
BATCH_SIZE      = 32
PHASE1_EPOCHS   = 25
PHASE2_EPOCHS   = 10
SEED            = 123

os.makedirs(EVAL_DIR, exist_ok=True)


# ─────────────────────────────────────────────
# STEP 1 — GLCM TEXTURE FEATURE EXTRACTION
# ─────────────────────────────────────────────
def extract_glcm_features(image_array):
    """
    Extract GLCM texture features from an image.
    Input : uint8 or float32 numpy array, any shape (H,W,3)
    Output: numpy array of shape (4,)
    """
    img = np.array(image_array)
    img = cv2.resize(img, (224, 224))
    if img.dtype != np.uint8:
        img = (img * 255).clip(0, 255).astype(np.uint8)
    # ✅ FIX 2: TF loads images as RGB — use COLOR_RGB2GRAY not BGR
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


def extract_texture_batch(image_batch):
    """Extract GLCM features for a batch of images (numpy arrays)."""
    return np.array([extract_glcm_features(img) for img in image_batch])


# ─────────────────────────────────────────────
# STEP 2 — DATASET AUDIT & LOADING
# ─────────────────────────────────────────────
def audit_dataset(dataset_path):
    """Print class distribution."""
    print("\n📊 Dataset Distribution:")
    class_counts = {}
    for cls in sorted(os.listdir(dataset_path)):
        cls_path = os.path.join(dataset_path, cls)
        if os.path.isdir(cls_path):
            count = len([f for f in os.listdir(cls_path)
                         if f.lower().endswith(('.jpg', '.jpeg', '.png'))])
            class_counts[cls] = count
            print(f"   {cls:<25} {count:>5} images")
    total = sum(class_counts.values())
    print(f"\n   Total: {total} images across {len(class_counts)} classes\n")
    return class_counts


def load_datasets(dataset_path):
    """Load train/val datasets."""
    kwargs = dict(
        validation_split=0.2,
        seed=SEED,
        image_size=IMG_SIZE,
        batch_size=BATCH_SIZE,
    )
    train_ds = tf.keras.preprocessing.image_dataset_from_directory(
        dataset_path, subset="training", **kwargs)
    val_ds = tf.keras.preprocessing.image_dataset_from_directory(
        dataset_path, subset="validation", **kwargs)

    class_names = train_ds.class_names
    print(f"✅ Detected Classes: {class_names}")
    return train_ds, val_ds, class_names


def get_class_weights(dataset_path, class_names):
    """Compute class weights to handle imbalance."""
    labels = []
    for i, cls in enumerate(class_names):
        cls_path = os.path.join(dataset_path, cls)
        if os.path.isdir(cls_path):
            count = len([f for f in os.listdir(cls_path)
                         if f.lower().endswith(('.jpg', '.jpeg', '.png'))])
            labels.extend([i] * count)

    weights = compute_class_weight('balanced', classes=np.unique(labels), y=labels)
    weight_dict = dict(enumerate(weights))
    named = {class_names[k]: round(v, 3) for k, v in weight_dict.items()}
    print(f"⚖️  Class Weights: {named}")
    return weight_dict


# ─────────────────────────────────────────────
# STEP 3 — AUGMENTATION
# ✅ FIX 3: Defined outside model so it does NOT run at inference/eval time
# ─────────────────────────────────────────────
augmentation_layer = tf.keras.Sequential([
    tf.keras.layers.RandomFlip("horizontal_and_vertical"),
    tf.keras.layers.RandomRotation(0.3),
    tf.keras.layers.RandomBrightness(0.2),
    tf.keras.layers.RandomContrast(0.2),
    tf.keras.layers.RandomZoom(0.1),
], name="augmentation")


# ─────────────────────────────────────────────
# STEP 4 — BUILD HYBRID MODEL
# ─────────────────────────────────────────────
def build_hybrid_model(num_classes):
    """
    Dual-input:
      Branch 1 : Image → MobileNetV2 → Dense(512)
      Branch 2 : GLCM (4,) → Dense(16)
      Merged   → Dense(64) → Dropout → Softmax
    Augmentation is NOT inside the model graph.
    """
    image_input = Input(shape=(224, 224, 3), name="image_input")
    # ✅ FIX 4: Rescaling to [-1,1] for MobileNetV2, applied BEFORE augmentation
    x = tf.keras.layers.Rescaling(1.0 / 127.5, offset=-1)(image_input)

    base_model = MobileNetV2(weights='imagenet', include_top=False,
                             input_shape=(224, 224, 3))
    base_model.trainable = False
    x = base_model(x, training=False)
    x = GlobalAveragePooling2D()(x)
    x = Dense(512, activation='relu')(x)

    texture_input = Input(shape=(4,), name="texture_input")
    t = Dense(16, activation='relu')(texture_input)

    merged = Concatenate()([x, t])
    merged = Dense(64, activation='relu')(merged)
    merged = Dropout(0.3)(merged)
    output = Dense(num_classes, activation='softmax')(merged)

    model = Model(inputs=[image_input, texture_input], outputs=output)
    return model, base_model


# ─────────────────────────────────────────────
# STEP 5 — SPECIALIST BINARY MODEL
# ─────────────────────────────────────────────
def build_specialist_model():
    """Binary classifier: Laterite=1, Red Soil=0."""
    base = MobileNetV2(weights='imagenet', include_top=False,
                       input_shape=(224, 224, 3))
    base.trainable = True

    inputs = Input(shape=(224, 224, 3))
    x = tf.keras.layers.Rescaling(1.0 / 127.5, offset=-1)(inputs)
    x = base(x, training=True)
    x = GlobalAveragePooling2D()(x)
    x = Dense(64, activation='relu')(x)
    x = Dropout(0.4)(x)
    output = Dense(1, activation='sigmoid')(x)

    return Model(inputs=inputs, outputs=output)


def train_specialist_model(dataset_path, class_names):
    """Train binary specialist on Laterite vs Red Soil only."""
    # ✅ FIX 5: Use underscore class names to match folder names on disk
    SPECIALIST_CLASSES = ["Laterite_Soil", "Red_Soil"]
    for cls in SPECIALIST_CLASSES:
        if cls not in class_names:
            print(f"⚠️  '{cls}' not found in dataset. Skipping specialist training.")
            return None

    specialist_path = "dataset/specialist_subset"

    for cls in SPECIALIST_CLASSES:
        src = os.path.join(dataset_path, cls)
        dst = os.path.join(specialist_path, cls)
        os.makedirs(dst, exist_ok=True)
        for fname in os.listdir(src):
            if fname.lower().endswith(('.jpg', '.jpeg', '.png')):
                src_file = os.path.join(src, fname)
                dst_file = os.path.join(dst, fname)
                if not os.path.exists(dst_file):
                    # ✅ FIX 6: shutil.copy2 instead of os.symlink — Windows-safe
                    shutil.copy2(src_file, dst_file)

    print("\n🔬 Training Specialist Model (Laterite vs Red Soil)...")
    common = dict(
        validation_split=0.2, seed=SEED,
        image_size=IMG_SIZE, batch_size=BATCH_SIZE,
        label_mode='binary'
    )
    spec_train = tf.keras.preprocessing.image_dataset_from_directory(
        specialist_path, subset="training", **common)
    spec_val = tf.keras.preprocessing.image_dataset_from_directory(
        specialist_path, subset="validation", **common)

    specialist = build_specialist_model()
    specialist.compile(
        optimizer=tf.keras.optimizers.Adam(1e-4),
        loss='binary_crossentropy',
        metrics=[
            'accuracy',
            tf.keras.metrics.Precision(name='precision'),
            tf.keras.metrics.Recall(name='recall'),
        ]
    )

    callbacks = [
        EarlyStopping(monitor='val_loss', patience=5, restore_best_weights=True),
        ReduceLROnPlateau(monitor='val_loss', factor=0.5, patience=3),
    ]

    specialist.fit(spec_train, validation_data=spec_val,
                   epochs=15, callbacks=callbacks)
    specialist.save(SPECIALIST_SAVE)
    print(f"✅ Specialist model saved → {SPECIALIST_SAVE}")
    return specialist


# ─────────────────────────────────────────────
# STEP 6 — PREPARE DATASETS WITH TEXTURE
# ─────────────────────────────────────────────
def prepare_with_texture(dataset, label=""):
    """
    Extract all images + labels from a tf.data pipeline,
    compute GLCM features, return numpy arrays for dual-input fit.
    """
    all_images, all_textures, all_labels = [], [], []
    desc = f" for {label} set" if label else ""
    print(f"   Extracting texture features{desc} (takes a few minutes)...")
    for batch_images, batch_labels in dataset:
        # ✅ FIX 7: Images come in as float32 [0,255] from image_dataset_from_directory
        #           Cast safely; extract_glcm_features handles both uint8 and float
        imgs = batch_images.numpy()
        for img, lbl in zip(imgs, batch_labels.numpy()):
            all_images.append(img)
            all_textures.append(extract_glcm_features(img))
            all_labels.append(lbl)
    return (np.array(all_images), np.array(all_textures)), np.array(all_labels)


# ─────────────────────────────────────────────
# STEP 7 — EVALUATION
# ─────────────────────────────────────────────
def evaluate_model(model, X_val, y_val, class_names, suffix="main"):
    """Confusion matrix, classification report, confidence plots."""
    print(f"\n📈 Evaluating {suffix} model...")
    images, textures = X_val
    preds_probs = model.predict([images, textures])
    preds = np.argmax(preds_probs, axis=1)

    # Confusion matrix
    cm = confusion_matrix(y_val, preds)
    disp = ConfusionMatrixDisplay(cm, display_labels=class_names)
    fig, ax = plt.subplots(figsize=(10, 8))
    disp.plot(ax=ax, xticks_rotation=45, colorbar=False)
    plt.title(f"Confusion Matrix — {suffix}")
    plt.tight_layout()
    cm_path = os.path.join(EVAL_DIR, f"confusion_matrix_{suffix}.png")
    plt.savefig(cm_path, dpi=150)
    plt.close()
    print(f"   Saved confusion matrix → {cm_path}")

    # Classification report
    report = classification_report(y_val, preds, target_names=class_names)
    print("\n📋 Classification Report:\n")
    print(report)
    report_path = os.path.join(EVAL_DIR, f"classification_report_{suffix}.txt")
    with open(report_path, 'w') as f:
        f.write(report)

    # Laterite ↔ Red Soil confusion breakdown
    # ✅ FIX 8: Use underscore names to match actual class_names from folder scan
    lat_idx = class_names.index("Laterite_Soil") if "Laterite_Soil" in class_names else -1
    red_idx = class_names.index("Red_Soil")      if "Red_Soil"      in class_names else -1
    if lat_idx >= 0 and red_idx >= 0:
        print(f"🔍 Laterite misclassified as Red Soil : {cm[lat_idx][red_idx]}")
        print(f"🔍 Red Soil misclassified as Laterite : {cm[red_idx][lat_idx]}")

        # Confidence distribution plots
        lat_mask = (y_val == lat_idx)
        red_mask = (y_val == red_idx)
        plt.figure(figsize=(10, 4))
        plt.subplot(1, 2, 1)
        plt.hist(preds_probs[lat_mask, lat_idx], bins=20, color='orange', edgecolor='k')
        plt.title("Laterite Soil — Confidence")
        plt.xlabel("Softmax Score"); plt.ylabel("Count")
        plt.subplot(1, 2, 2)
        plt.hist(preds_probs[red_mask, red_idx], bins=20, color='red', edgecolor='k')
        plt.title("Red Soil — Confidence")
        plt.xlabel("Softmax Score"); plt.ylabel("Count")
        plt.tight_layout()
        conf_path = os.path.join(EVAL_DIR, "confidence_distribution.png")
        plt.savefig(conf_path, dpi=150)
        plt.close()
        print(f"   Saved confidence distribution → {conf_path}")


# ─────────────────────────────────────────────
# MAIN TRAINING PIPELINE
# ─────────────────────────────────────────────
def train_real_model(dataset_path=DATASET_PATH, save_path=MODEL_SAVE):

    # Audit & load
    audit_dataset(dataset_path)
    train_ds, val_ds, class_names = load_datasets(dataset_path)
    class_weight_dict = get_class_weights(dataset_path, class_names)
    num_classes = len(class_names)

    # Build model
    print("\n🏗️  Building Hybrid MobileNetV2 + Texture model...")
    model, base_model = build_hybrid_model(num_classes)
    model.summary()

    # ── PHASE 1: Train head only ────────────────────────────────────
    print("\n🔒 PHASE 1 — Training classification head (base frozen)...")
    model.compile(
        optimizer=tf.keras.optimizers.Adam(1e-3),
        loss=tf.keras.losses.SparseCategoricalCrossentropy(from_logits=False),
        metrics=['accuracy']
    )

    print("   Preparing texture features for training set...")
    X_train_raw, y_train = prepare_with_texture(train_ds, label="training")
    print("   Preparing texture features for validation set...")
    X_val_raw,   y_val   = prepare_with_texture(val_ds,   label="validation")

    print("   Scaling texture features...")
    scaler = StandardScaler()
    X_train_tex_scaled = scaler.fit_transform(X_train_raw[1])
    X_val_tex_scaled   = scaler.transform(X_val_raw[1])

    # Persist the scaler so inference in analyzer.py uses identical scaling
    joblib.dump(scaler, "scaler.pkl")
    print("   ✅ Scaler saved → scaler.pkl")

    X_train = (X_train_raw[0], X_train_tex_scaled)
    X_val   = (X_val_raw[0],   X_val_tex_scaled)

    print("📊 Verifying label alignment for first 5 samples...")
    for i in range(min(5, len(y_train))):
        print(f"   Sample {i}: Label {y_train[i]} ({class_names[y_train[i]]})")

    callbacks_p1 = [
        EarlyStopping(monitor='val_accuracy', patience=5, restore_best_weights=True),
        ReduceLROnPlateau(monitor='val_loss', factor=0.5, patience=3, verbose=1),
    ]

    model.fit(
        x=[X_train[0], X_train[1]], y=y_train,
        validation_data=([X_val[0], X_val[1]], y_val),
        epochs=PHASE1_EPOCHS,
        class_weight=class_weight_dict,
        callbacks=callbacks_p1,
        batch_size=BATCH_SIZE,
    )

    # ── PHASE 2: Fine-tune last 30 layers ──────────────────────────
    print("\n🔓 PHASE 2 — Fine-tuning last 30 layers of MobileNetV2...")
    base_model.trainable = True
    for layer in base_model.layers[:-30]:
        layer.trainable = False

    model.compile(
        optimizer=tf.keras.optimizers.Adam(1e-5),
        loss=tf.keras.losses.SparseCategoricalCrossentropy(from_logits=False),
        metrics=['accuracy']
    )

    callbacks_p2 = [
        EarlyStopping(monitor='val_accuracy', patience=5, restore_best_weights=True),
        ReduceLROnPlateau(monitor='val_loss', factor=0.5, patience=3, verbose=1),
    ]

    model.fit(
        x=[X_train[0], X_train[1]], y=y_train,
        validation_data=([X_val[0], X_val[1]], y_val),
        epochs=PHASE2_EPOCHS,
        class_weight=class_weight_dict,
        callbacks=callbacks_p2,
        batch_size=BATCH_SIZE,
    )

    # Save
    model.save(save_path)
    print(f"\n✅ Main hybrid model saved → {save_path}")

    # Evaluate
    evaluate_model(model, X_val, y_val, class_names, suffix="hybrid")

    # Specialist
    train_specialist_model(dataset_path, class_names)

    print("\n🎉 Training pipeline complete!")
    print(f"   Main model  : {save_path}")
    print(f"   Specialist  : {SPECIALIST_SAVE}")
    print(f"   Scaler      : scaler.pkl")
    print(f"   Evaluation  : {EVAL_DIR}/")


# ─────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────
if __name__ == "__main__":
    import ssl
    ssl._create_default_https_context = ssl._create_unverified_context

    if os.path.exists("dataset"):
        train_real_model()
    else:
        print("ERROR: 'dataset/' folder not found.")
        print("Place data at: terra_layer/dataset/CyAUG-Dataset/<class_name>/<images>")