from PIL import Image

MAX_LOGO_SIZE = (640, 480)


def fit_logo(image_field):
    if not image_field or not image_field.storage.exists(image_field.name):
        return
    with Image.open(image_field.path) as image:
        if image.width <= MAX_LOGO_SIZE[0] and image.height <= MAX_LOGO_SIZE[1]:
            return
        image.thumbnail(MAX_LOGO_SIZE)
        image.save(image_field.path)
