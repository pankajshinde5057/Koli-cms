import qrcode
from io import BytesIO
from django.core.files import File

def generate_qr_code(data, filename):
    qr = qrcode.make(data)
    blob = BytesIO()
    qr.save(blob, format='PNG')
    return File(blob, name=filename)
