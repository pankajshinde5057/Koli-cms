import face_recognition
import numpy as np
from PIL import Image


def get_face_encoding(image_path):
    image = face_recognition.load_image_file(image_path)
    encodings = face_recognition.face_encodings(image)
    if encodings:
        return encodings[0] # numpy aaray
    return None

