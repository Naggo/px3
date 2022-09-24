from PIL import Image
import console
import shutil

tga_mode = False


num = console.alert('Select image', '', '1', '2', '3')
if tga_mode:
	img = Image.open(f'files/save_{num}.png')
	img.save(f'3_image{num}.tga')
else:
	shutil.copy(f'files/save_{num}.png', f'3_image{num}.png')
