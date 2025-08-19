import cv2
import numpy as np
import os
from django.conf import settings
from main_app.models import FaceProfile

# Load Haar Cascade for face detection
face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')

def extract_face(image_path):
    img = cv2.imread(image_path)
    if img is None:
        return None

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    faces = face_cascade.detectMultiScale(gray, 1.1, 4)

    if len(faces) == 0:
        return None

    x, y, w, h = faces[0]
    face = gray[y:y+h, x:x+w]
    face = cv2.resize(face, (200, 200))
    return face

def match_face_with_database(upload_path, threshold=60):
    # Extract face from uploaded image
    target_face = extract_face(upload_path)
    if target_face is None:
        return None

    recognizer = cv2.face.LBPHFaceRecognizer_create()

    training_faces = []
    labels = []
    label_to_user = {}

    for profile in FaceProfile.objects.select_related('employee'):
        registered_face = extract_face(profile.face_image.path)
        if registered_face is not None:
            label_id = profile.employee.id
            training_faces.append(registered_face)
            labels.append(label_id)
            label_to_user[label_id] = profile.employee

    if not training_faces:
        return None

    recognizer.train(training_faces, np.array(labels))

    label, confidence = recognizer.predict(target_face)

    if confidence < threshold:
        return label_to_user.get(label)
    return None