# from barcode import Code128
# from barcode.writer import ImageWriter
# from io import BytesIO
# from django.core.files.uploadedfile import InMemoryUploadedFile
# from django.urls import reverse


# def generate_barcode(asset_id):
#     url = reverse('asset_app:assets-detail', kwargs={'pk': asset_id})

#     writer = ImageWriter()
#     barcode_instance = Code128(url, writer=writer)

#     render_options = {
#         'write_text': False,
#         'module_width': 0.2,
#         'module_height': 15.0,
#     }
    
#     barcode_image = barcode_instance.render(writer_options=render_options)

#     barcode_io = BytesIO()
#     barcode_image.save(barcode_io, 'PNG')
#     barcode_io.seek(0)

#     return InMemoryUploadedFile(
#         barcode_io, None, f'{asset_id}_barcode.png', 'image/png', barcode_io.getbuffer().nbytes, None
#     )




from barcode import Code128
from barcode.writer import ImageWriter
from io import BytesIO
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.urls import reverse
from pylibdmtx.pylibdmtx import encode
from PIL import Image

def generate_barcode(asset_id):
    # url = f'http://192.168.1.56:8000/asset-app/asset/{asset_id}/detail'
    url = reverse('asset_app:assets-detail', kwargs={'pk': asset_id})
    encoded = encode(url.encode('utf8'))
    
    barcode_image = Image.frombytes('RGB', (encoded.width, encoded.height), encoded.pixels)
    barcode_io = BytesIO()
    barcode_image.save(barcode_io, 'PNG')
    barcode_io.seek(0)

    return InMemoryUploadedFile(
        barcode_io, None, f'{asset_id}_barcode.png', 'image/png', barcode_io.getbuffer().nbytes, None
    )

