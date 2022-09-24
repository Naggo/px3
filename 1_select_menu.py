from PIL import Image
import ui
import scene
import os
import shutil
import dialogs
import json
from draw import MyScene
from my_funcs import pil2ui
FOLDERS = "files/save_data"
latest = 'latest.txt'


def num_folder(name):
	num = 1
	if ' ' in name:
		front, back = name.rsplit(' ', 1)
		if back.isdecimal():
			name = front
			num = int(back)
	
	while os.path.exists(f'{FOLDERS}/{name} {num}'):
		num += 1
	return f'{name} {num}'

v = None
dirs = {}
cur_key = None
next_key = 0

	
def ok(sender):
	if cur_key is None:
		return
	path = dirs[cur_key][0]
	if os.path.exists(os.path.join(FOLDERS, path)):
		with open(latest, mode="w") as f:
			f.write(path)
		
		MyScene.folder_name = path
		v.close()
		v.wait_modal()
		scene.run(MyScene(), show_fps=True)
	

def new_dir(sender):
	global next_key
	
	name = num_folder('folder')
	name = dialogs.input_alert("folder name", "", name)
	if name is None:
		return
	name = name.replace("/", "_")
	path = os.path.join(FOLDERS, name)
	
	try:
		shutil.copytree('files/sample_data', path)
	except FileExistsError:
		dialogs.hud_alert("Existing", 'error', 1)
		return
	
	lays = Image.open(os.path.join(path, 'layers.png'))
	with open(os.path.join(path, 'data.json')) as f:
		data = json.load(f)
	lay_dict = data["layers"]["0"]
	y = lay_dict["y"]
	w = lay_dict["w"]
	h = lay_dict["h"]
	img = lays.transform((w, h), Image.EXTENT, (0, y, w, y + h))
	
	length = len(dirs)
	dirs[next_key] = (name, length)
	add_view(next_key, length, img)
	next_key += 1
	

def copy_dir(sender):
	global next_key
	
	if cur_key is None:
		return
	c = dialogs.alert("Confirm", "", "Copy")
	if c == 0:
		return
	
	name = dirs[cur_key][0]
	path = os.path.join(FOLDERS, name)
	new_name = num_folder(name)
	shutil.copytree(path, os.path.join(FOLDERS, new_name))
	
	lays = Image.open(os.path.join(path, 'layers.png'))
	with open(os.path.join(path, 'data.json')) as f:
		data = json.load(f)
	lay_dict = data["layers"]["0"]
	y = lay_dict["y"]
	w = lay_dict["w"]
	h = lay_dict["h"]
	img = lays.transform((w, h), Image.EXTENT, (0, y, w, y + h))
	
	length = len(dirs)
	dirs[next_key] = (new_name, length)
	add_view(next_key, length, img)
	next_key += 1
	

def delete_dir(sender):
	global cur_key
	
	if cur_key is None:
		return
	c = dialogs.alert("Confirm", "", "Delete")
	if c == 0:
		return
	
	scroll = v['scroll']
	num = dirs[cur_key][1]
	
	shutil.rmtree(os.path.join(FOLDERS, dirs[cur_key][0]))
	del dirs[cur_key]
	img_v = scroll[f'img_{cur_key}']
	bt_v = scroll[f'dir_{cur_key}']
	scroll.remove_subview(img_v)
	scroll.remove_subview(bt_v)
	cur_key = None
	
	for key, value in dirs.items():
		if value[1] > num:
			value = (value[0], value[1] - 1)
			img_v = scroll[f'img_{key}']
			bt_v = scroll[f'dir_{key}']
			img_v.y -= 80
			bt_v.y -= 80
	

def rename_dir(sender):
	if cur_key is None:
		return
	old_name = dirs[cur_key][0]
	new_name = dialogs.input_alert("folder name", "", old_name)
	if new_name is None:
		return
	new_name = new_name.replace("/", "_")
	
	try:
		os.rename(os.path.join(FOLDERS, old_name), os.path.join(FOLDERS, new_name))
	except OSError:
		dialogs.hud_alert("Existing", 'error', 1)
		return
	
	dirs[cur_key] = (new_name, dirs[cur_key][1])
	bt_v = v['scroll'][f'dir_{cur_key}']
	bt_v.title = new_name
	

def select_dir(sender):
	global cur_key
	
	if cur_key is not None:
		bt_prev = v['scroll'][f'dir_{cur_key}']
		bt_prev.action = select_dir
		bt_prev.border_width = 1
		bt_prev.border_color = '#000000'
	cur_key = int(sender.name.split("_")[1])
	sender.action = None
	sender.border_width = 3
	sender.border_color = '#77ff55'
	

def add_view(key, num, img):
	length = len(dirs)
	scroll = v['scroll']
	scroll.content_size = (320, max(320, length * 80 + 16))
	
	ui_img = pil2ui(img)
	y = num * 80 + 16
	
	img_v = ui.ImageView()
	img_v.frame = (16, y, 64, 64)
	img_v.border_width = 1
	img_v.name = f"img_{key}"
	img_v.image = ui_img
	scroll.add_subview(img_v)
	
	bt_v = ui.Button()
	bt_v.frame = (96, y, 208, 64)
	bt_v.border_width = 1
	bt_v.name = f"dir_{key}"
	bt_v.title = dirs[key][0]
	bt_v.action = select_dir
	scroll.add_subview(bt_v)


def load_ui():
	global v, dirs, cur_key, next_key
	
	dir_list = os.listdir(FOLDERS)
	dir_list.sort()
	length = len(dir_list)
	ranlen = range(length)
	
	dirs = dict(zip(ranlen, zip(dir_list, ranlen)))
	cur_key = None
	next_key = length

	v = ui.load_view()
	
	for key, value in dirs.items():
		path = value[0]
		
		lays = Image.open(os.path.join(FOLDERS, path, 'layers.png'))
		with open(os.path.join(FOLDERS, path, 'data.json')) as f:
			data = json.load(f)
		lay_dict = data["layers"]["0"]
		
		y = lay_dict["y"]
		w = lay_dict["w"]
		h = lay_dict["h"]
		img = lays.transform((w, h), Image.EXTENT, (0, y, w, y + h))
		
		add_view(key, value[1], img)
	
	v.corner_radius = 10
	v.border_color = '#6699cc'
	v.border_width = 2
	v.present('sheet', False)

if __name__ == '__main__':
	load_ui()
