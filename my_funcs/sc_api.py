import base64
import io
import json
import shortcuts


def img2b64(img):
	with io.BytesIO() as f:
		img.save(f, format='png')
		img_data = f.getvalue()
	return base64.standard_b64encode(img_data)


def sc_gif(frames, duration=0.2):
	data = {
		"duration": duration,
		"frames": [img2b64(im).decode('utf-8') for im in frames]
	}
	shortcuts.open_shortcuts_app('py_gif', json.dumps(data))


def open_pythonista(path):
	shortcuts.open_shortcuts_app('open_pythonista', path)
