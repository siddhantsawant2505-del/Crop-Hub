import os
import tensorflow as tf

def clean_directory(directory):
    print(f"Cleaning directory: {directory}")
    num_skipped = 0
    num_deleted = 0
    
    for root, dirs, files in os.walk(directory):
        for filename in files:
            filepath = os.path.join(root, filename)
            try:
                # Try to load and decode the image
                img_bytes = tf.io.read_file(filepath)
                # This will raise an error if the format is unknown/corrupted
                tf.io.decode_image(img_bytes)
            except Exception as e:
                print(f"Deleting invalid image: {filepath} - Reason: {e}")
                os.remove(filepath)
                num_deleted += 1
                continue
            
            # Additional check for common non-image extensions if necessary
            ext = os.path.splitext(filename)[1].lower()
            if ext not in ['.jpg', '.jpeg', '.png', '.bmp', '.gif']:
                print(f"Deleting unsupported file extension: {filepath}")
                os.remove(filepath)
                num_deleted += 1
                
    print(f"Done! Deleted {num_deleted} invalid/unsupported files.")

if __name__ == "__main__":
    import ssl
    ssl._create_default_https_context = ssl._create_unverified_context
    
    base_dir = "dataset"
    if os.path.exists(base_dir):
        # We clean both subfolders
        clean_directory(os.path.join(base_dir, "CyAUG-Dataset"))
        clean_directory(os.path.join(base_dir, "Orignal-Dataset"))
    else:
        print(f"Error: {base_dir} not found.")
