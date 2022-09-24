from PIL import Image
import json


layers = Image.new("RGBA", (32, 32), (0, 0, 0, 0))
data = {
	"bg_color": "#FFFFFF",
	"color_type": 0,
	"grid_size": [4, 4],
	"display_grid": False,
	"display_alert": True,
	"auto_tool": True,
	"play_sound": True,
	"zoom": 8,
	"selected": 0,
	"layers": {"0": {"y": 0, "w": 32, "h": 32, "a": 1.0}},
	"palette": {
		"0": [0, 0, 0, 255], "1": [255, 0, 0, 255],
		"2": [0, 255, 0, 255], "3": [0, 0, 255, 255],
		"4": [0, 255, 255, 255], "5": [255, 0, 255, 255],
		"6": [255, 255, 0, 255], "7": [128, 128, 255, 255]
	}
}
palettes = Image.new("RGBA", (8, 1), (0, 0, 0, 0))
palettes.putdata([
	(0, 0, 0, 255), (255, 0, 0, 255),
	(0, 255, 0, 255), (0, 0, 255, 255),
	(0, 255, 255, 255), (255, 0, 255, 255),
	(255, 255, 0, 255), (128, 128, 255, 255)
])

layers.save('files/sample_data/layers.png', 'png')
palettes.save('files/sample_data/palettes.png', 'png')
	
with open('files/sample_data/data.json', 'w') as f:
	json.dump(data, f, indent=2)
