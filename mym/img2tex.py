from PIL import Image
import io
import scene
import ui


__all__ = ["img2ui", "img2tex"]


def img2ui(img: Image.Image) -> ui.Image:
	with io.BytesIO() as f:
		img.save(f, format="png")
		buffer_img = f.getvalue()
	return ui.Image.from_data(buffer_img)


def img2tex(img: Image.Image) -> scene.Texture:
	with io.BytesIO() as f:
		img.save(f, format="bmp")
		buffer_img = f.getvalue()
	ui_img = ui.Image.from_data(buffer_img)
	return scene.Texture(ui_img)
