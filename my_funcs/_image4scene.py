from PIL import Image, ImageChops


def image4scene(img: Image.Image) -> Image.Image:
	r, g, b, a = img.split()
	r = ImageChops.multiply(r, a)
	g = ImageChops.multiply(g, a)
	b = ImageChops.multiply(b, a)
	return Image.merge("RGBA", (r, g, b, a))
