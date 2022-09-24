from PIL import Image
import io
import scene
import ui


def pil2ui(img: Image.Image) -> ui.Image:
	with io.BytesIO() as f:
		img.save(f, format='PNG')
		buffer_img = f.getvalue()
	return ui.Image.from_data(buffer_img)


def pil2tex(img: Image.Image) -> scene.Texture:
	ui_img = pil2ui(img)
	return scene.Texture(ui_img)
