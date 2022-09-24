from PIL import Image, ImageChops, ImageColor, ImageDraw, GifImagePlugin
import numpy as np

from scene import *
import sound
import ui

from collections.abc import Sequence
from typing import NamedTuple

import clipboard
import datetime
import dialogs
import json
import math
import os

from my_files import my_files
from my_funcs import pil2ui, image4scene, sc_gif
from my_nodes import ButtonNode, TTLNode
from my_views import MoveView

from mym.img2tex import img2tex, img2ui
pil2tex = img2tex
pil2ui = img2ui

A = Action

# Inspired by:
# *Pixel Editor (by Daniel X Moore)
# *dotpict
# *PEKO STEP


# 解決策が見つかるまでこれが必須になる
ButtonNode.buttons.clear()
# print(ButtonNode.buttons)

WHITE = (1.0, 1.0, 1.0, 1.0)
LIGHT_GRAY = (0.8, 0.8, 0.8, 1.0)
GRAY = (0.6, 0.6, 0.6, 1.0)
BLACK = (0.0, 0.0, 0.0, 1.0)
CLEAR = (0, 0, 0, 0)

MODE_DEFAULT = 0
MODE_MOVE = 1
MODE_DRAW = 2
MODE_GUI = 3

TOOL_PENCIL = 0
TOOL_ERASER = 1
TOOL_PICKER = 2
TOOL_CAP = 3
TOOL_FILL = 4
TOOL_RECT = 5
TOOL_CIRCLE = 6
TOOL_LINE = 7
TOOL_MOVE = 8


class UndoData:
	__slots__ = ['type', 'key', 'number', 'image']
	
	def __init__(self, type):
		assert type in {"sub", "image", "add_layer", "remove_layer"}
		self.type = type
		self.key = None
		self.number = None
		self.image = None


class Layer:
	__slots__ = ['image', 'node', 'number']
	
	def __init__(self, img, number=0):
		self.image = img
		self.node = SpriteNode(anchor_point=(0, 1))
		self.node.z_position = number
		self.number = int(number)
		self.pil2tex()
	
	def pil2tex(self):
		texture_img = pil2tex(image4scene(self.image))
		texture_img.filtering_mode = FILTERING_NEAREST
		self.node.texture = texture_img


class Gui(ButtonNode):
	buttons = []
	
	def __init__(self, parent, size, tex, **kwargs):
		ButtonNode.__init__(self, tex, parent=parent, **kwargs)
		if self.texture:
			self.texture.filtering_mode = FILTERING_NEAREST
		self.x_scale = size / self.size[0]
		self.y_scale = size / self.size[1]
		self.z_position = 255
	
	def change_texture(self, tex):
		self.texture = Texture(tex)
		self.texture.filtering_mode = FILTERING_NEAREST


class GuiColor(Gui):
	def __init__(self, parent, size, color, key):
		Gui.__init__(self, parent, size, None)
		self.change_color(color)
		self.label = LabelNode()
		self.label.x_scale = self.x_scale * 4
		self.label.y_scale = self.y_scale * 4
		self.label.position = self.position
		self.add_child(self.label)
		self.key = key
	
	def change_color(self, color):
		self.normal_color = color
		if isinstance(color, str):
			rgb = tuple(v / 255 for v in ImageColor.getrgb(color))
		else:
			rgb = color
		if sum(rgb) < 0.5:
			self.pushed_color = tuple(v + 0.2 for v in rgb)
		else:
			self.pushed_color = tuple(v - 0.3 for v in rgb)
	
	def set_alpha(self, alpha):
		if alpha == 255:
			self.label.alpha = 0
		else:
			self.label.alpha = 1
		self.label.text = str(alpha)
		self.label.color = tuple([min(1, 1.5 - c) for c in self.color])


class Pixel(NamedTuple):
	x: int = 0
	y: int = 0
	
	def __add__(self, other):
		if isinstance(other, Sequence):
			return Pixel(self[0] + other[0], self[1] + other[1])
		else:
			return Pixel(self[0] + other, self[1] + other)
	
	def __sub__(self, other):
		if isinstance(other, Sequence):
			return Pixel(self[0] - other[0], self[1] - other[1])
		else:
			return Pixel(self[0] - other, self[1] - other)
	
	def __mul__(self, other):
		if isinstance(other, Sequence):
			return Pixel(self[0] * other[0], self[1] * other[1])
		else:
			return Pixel(self[0] * other, self[1] * other)
	
	def __truediv__(self, other):
		return self.__floordiv__(other)
	
	def __floordiv__(self, other):
		if isinstance(other, Sequence):
			return Pixel(self[0] // other[0], self[1] // other[1])
		else:
			return Pixel(self[0] // other, self[1] // other)

# ---:


class MyScene (Scene):
	folder_name = 'folder 1'
	
	def setup(self):
		# 属性
		self.background_color = (0.3, 0.3, 0.3)
		
		self.wait = True
		self.set_gui()
		
		self.mode = MODE_DEFAULT
		self.tool = TOOL_PENCIL
		self.tool_prev = TOOL_PENCIL
		self.tool_gui = self.gui_pencil
		
		self.messages = []
		self.switching = False
		
		self.layers = {}
		self.cur_key = 0
		self.next_key = 0
		
		self.undo_list = []
		self.undo_index = -1
		self.undo_limit = 100
		
		self.move_start = Point(0, 0)
		self.move = Vector2(0, 0)
		self.touch_x = 0.0
		self.touch_y = 0.0
		
		self.draw_start_point = Pixel(0, 0)
		self.draw_point = Pixel(0, 0)
		self.draw_prev_point = Pixel(-5, -5)
		self.draw_method = self.draw_pencil
		
		self.cap_img_p = None
		self.cap_img_s = None
		self.cap_stage = 0
		self.cap_point = Pixel(0, 0)
		
		self.colors = {
			0: (0, 0, 0, 255), 1: (255, 0, 0, 255),
			2: (0, 255, 0, 255), 3: (0, 0, 255, 255),
			4: (0, 255, 255, 255), 5: (255, 0, 255, 255),
			6: (255, 255, 0, 255), 7: (128, 128, 255, 255)
		}
		self.choose_color(0)
		
		# self.color_key
		# self.col_ov
		# self.col_c
		
		self.touch_id = None
		
		self.erase_rect = False
		self.pick_alpha = False
		self.cap_cut = False
		self.rect_fill = True
		self.circle_fill = True
		
		self.play_sound = True
		
		# ここからいろいろ
		folder_path = f'files/save_data/{self.folder_name}'
		sample_path = 'files/sample_data'
		
		# フォルダの確認
		if not os.path.exists(folder_path):
			tx = (
				f"<st:cyan::{self.folder_name}>が見つかりません。\n"
				"新しく作成します。")
			self.new_message(tx)
			os.mkdir(folder_path)
		
		tx = ''
		# 画像の読み込み
		try:
			img = Image.open(f'{folder_path}/layers.png')
		except FileNotFoundError:
			tx += '画像ファイルが見つかりません。\n'
			img = Image.open(f'{sample_path}/layers.png')
		
		# データの読み込み
		try:
			with open(f'{folder_path}/data.json', 'r') as f:
				data = json.load(f)
		except FileNotFoundError:
			tx += 'JSONファイルが見つかりません。\n'
			with open(f'{sample_path}/data.json', 'r') as f:
				data = json.load(f)
			data["layers"]["0"]["w"] = img.size[0]
			data["layers"]["0"]["h"] = img.size[1]
		
		if tx:
			tx += '>サンプルデータをロードしました。'
			self.new_message(tx)
		
		# レイヤーの設定
		self.cur_key = data["selected"]
		self.next_key = len(data["layers"])
		for k, v in data["layers"].items():
			y = v["y"]
			w = v["w"]
			h = v["h"]
			img2 = img.transform((w, h), Image.EXTENT, (0, y, w, y + h))
			number = int(k)
			try:
				lay = Layer(img2, number)
			except ValueError:
				w = min(w, 256)
				h = min(h, 256)
				img2 = img.transform((w, h), Image.EXTENT, (0, y, w, y + h))
				number = int(k)
				lay = Layer(img2, number)
				self.new_message(
					'エラーが発生した為、\n'
					'画像サイズを256pxに変更しました。')
			lay.node.alpha = v["a"]
			self.layers[number] = lay
		
		# パレットの設定
		plt = {int(k): tuple(v) for k, v in data["palette"].items()}
		self.set_palette(plt)
		
		# オプション設定
		self.bg_color = data["bg_color"]
		self.color_type = data["color_type"]
		self.grid_size = tuple(data["grid_size"])
		self.display_grid = data["display_grid"]
		self.display_alert = data["display_alert"]
		self.auto_tool = data["auto_tool"]
		self.play_sound = data["play_sound"]
		
		# 拡大の設定
		self.zoom = data["zoom"]
		if self.zoom == 128:
			self.gui_zoom_in.normal_color = LIGHT_GRAY
		elif self.zoom == 1:
			self.gui_zoom_out.normal_color = LIGHT_GRAY
		
		# グリッドの追加
		grid_path = ui.Path.rect(0, 0, 0, 0)
		self.grid = ShapeNode(grid_path, anchor_point=(0, 1))
		self.thick_grid = ShapeNode(grid_path, anchor_point=(0, 1))
		self.grid.add_child(self.thick_grid)
		self.add_child(self.grid)
		
		# レイヤー関係諸々
		self.img_bg = SpriteNode(parent=self, anchor_point=(0, 1))
		self.img_bg.z_position = -1
		self.img_bg.color = self.bg_color
		
		self.ov = Layer(Image.new("RGBA", (16, 16), CLEAR))
		self.ov.node.z_position = self.cur_key + 0.5
		self.img_bg.add_child(self.ov.node)
		
		self.draw_ov = ImageDraw.Draw(self.ov.image)
		
		for key, lay in self.layers.items():
			self.selector_add(key)
			if key == self.cur_key:
				self.new_image(lay)
			else:
				lay.pil2tex()
			self.img_bg.add_child(lay.node)
		
		# セットアップおわり
		self.gui_undo.normal_color = LIGHT_GRAY
		self.gui_redo.normal_color = LIGHT_GRAY
		self.gui_pencil.normal_color = GRAY
		self.grid_color()
		
		assert self.cur_key < len(self.layers) == self.next_key
		
		self.wait = False
	
	def did_change_size(self):
		pass
	
	def update(self):
		if self.mode is MODE_DRAW and self.draw_point != self.draw_prev_point:
			self.draw_method()
			self.draw_prev_point = self.draw_point
	
	def stop(self):
		folder_path = f'files/save_data/{self.folder_name}'
		w = 1
		h = 0
		for lay in self.layers.values():
			w = max(w, lay.image.size[0])
			h += lay.image.size[1]
		img = Image.new("RGBA", (w, max(1, h)), CLEAR)
		
		y = 0
		dict_layers = {}
		for key, lay in self.layers.items():
			img.paste(lay.image, (0, y))
			w, h = lay.image.size
			a = lay.node.alpha
			dict_lay = {"y": y, "w": w, "h": h, "a": a}
			y += h
			dict_layers[lay.number] = dict_lay
		img.save(f'{folder_path}/layers.png', 'png')
		
		dict_data = {
			"bg_color": self.bg_color,
			"color_type": self.color_type,
			"grid_size": self.grid_size,
			"display_grid": self.display_grid,
			"display_alert": self.display_alert,
			"auto_tool": self.auto_tool,
			"play_sound": self.play_sound,
			"zoom": self.zoom,
			"selected": self.current_layer().number,
			"layers": dict_layers,
			"palette": self.colors
			}
		with open(f'{folder_path}/data.json', 'w') as f:
			json.dump(dict_data, f, indent=2)
	
	# ---:
	
	def new_message(self, text):
		if self.messages:
			self.messages.append(text)
		else:
			self.messages.append(text)
			self.show_message(text)
	
	def show_message(self, text):
		w, h = self.size
		text = '<mv::2>' + text
		
		self.ttl = TTLNode(text, (f'{my_files}/fonts/k8x12.ttf', 24))
		self.ttl.filtering_mode = FILTERING_NEAREST
		self.ttl.bg_color = (0, 0, 0, 64)
		self.ttl.new_image()
		self.ttl.position = ((w - self.ttl.size[0]) / 2, h)
		self.ttl.z_position = 254
		self.ttl.when_stopped = self.fade_message
		self.add_child(self.ttl)
		
		self.close_bt = ButtonNode('iow:ios7_close_outline_32')
		self.close_bt.anchor_point = (0, 0)
		self.close_bt.position = (
			self.ttl.frame.max_x, min(self.ttl.frame.min_y, h - 32))
		self.close_bt.z_position = 254
		self.close_bt.action = self.remove_message
		self.add_child(self.close_bt)
		
		self.ttl.interval = 0.0005
		if self.play_sound:
			self.ttl.sound_effect = ('ui:click5', 0.6)
		self.ttl.auto_start()
	
	def fade_message(self):
		fading = A.sequence(A.wait(11), A.fade_to(0, 1), A.call(self.remove_message))
		self.ttl.run_action(fading)
	
	def remove_message(self, bt=None):
		self.ttl.remove_all_actions()
		self.ttl.remove_from_parent()
		self.close_bt.remove_from_parent()
		self.messages.pop(0)
		if self.messages:
			self.show_message(self.messages[0])
		else:
			del self.ttl
			del self.close_bt
	
	# ---:
	
	def draw_pencil(self):
		if self.draw_prev_point != (-5, -5):
			self.draw_ov.line([self.draw_prev_point, self.draw_point], self.col_ov)
		else:
			self.draw_ov.point(self.draw_point, self.col_ov)
		self.ov.pil2tex()
	
	def draw_eraser(self):
		if self.erase_rect:
			self.ov.image.paste(CLEAR)
			self.draw_ov.rectangle([self.draw_start_point, self.draw_point], fill=self.bg_color)
		else:
			if self.draw_prev_point != (-5, -5):
				self.draw_ov.line([self.draw_prev_point, self.draw_point], self.bg_color)
			else:
				self.draw_ov.point(self.draw_point, self.bg_color)
		self.ov.pil2tex()
	
	def pick_color(self):
		cul = self.current_layer()
		x_in = 0 <= self.draw_point.x < cul.image.size[0]
		y_in = 0 <= self.draw_point.y < cul.image.size[1]
		if not (x_in and y_in):
			return
		
		col = cul.image.getpixel(self.draw_point)
		if self.pick_alpha:
			opc = col[3]
		else:
			opc = self.colors[self.color_key][3]
		col = col[0:3]
		
		gui_color = getattr(self, f'gui_color{self.color_key}')
		gui_color.change_color(tuple(c / 255 for c in col))
		if self.pick_alpha:
			gui_color.set_alpha(opc)
		
		self.colors[self.color_key] = (*col, opc)
		
		self.choose_color(self.color_key)
	
	def copy_and_paste(self):
		self.ov.image.paste(CLEAR)
		
		if self.cap_stage == 0:
			self.draw_ov.rectangle([self.draw_start_point, self.draw_point], outline=self.col_c)
			
		elif self.cap_stage == 2:
			box = tuple(self.draw_point - Pixel._make(self.cap_img_p.size) // 2)
			self.ov.image.paste(self.cap_img_s, box)
		
		# 1&3
		else:
			if self.cap_cut and self.cap_stage == 1:
				box = (*self.cap_point, *(self.cap_point + self.cap_img_p.size))
				self.ov.image.paste(self.bg_color, box)
			move = self.draw_start_point - self.draw_point
			min_point = tuple(self.cap_point - move)
			self.ov.image.paste(self.cap_img_s, min_point)
			
		self.ov.pil2tex()
	
	def draw_fill(self):
		cul = self.current_layer()
		x_in = 0 <= self.draw_point.x < cul.image.size[0]
		y_in = 0 <= self.draw_point.y < cul.image.size[1]
		if not (x_in and y_in):
			return
			
		img = cul.image.copy()
		color = img.getpixel(self.draw_point)
		if color != self.col_ov:
			ImageDraw.floodfill(img, self.draw_point, self.col_ov)
		
		if self.undo_save("sub", cul.image, img, self.cur_key):
			cul.image = img
			cul.pil2tex()
			self.selector_img(self.cur_key)
	
	def draw_rect(self):
		self.ov.image.paste(CLEAR)
		
		if self.rect_fill:
			self.draw_ov.rectangle([self.draw_start_point, self.draw_point], fill=self.col_ov)
		else:
			self.draw_ov.rectangle([self.draw_start_point, self.draw_point], outline=self.col_ov)
		self.ov.pil2tex()
	
	def draw_circle(self):
		x0, y0 = self.draw_start_point
		x1, y1 = self.draw_point
		min_xy = (min(x0, x1), min(y0, y1))
		max_xy = (max(x0, x1), max(y0, y1))
		self.ov.image.paste(CLEAR)
		
		if self.circle_fill:
			self.draw_ov.ellipse([min_xy, max_xy], fill=self.col_ov)
		else:
			self.draw_ov.ellipse([min_xy, max_xy], outline=self.col_ov)
		self.ov.pil2tex()
	
	def draw_line(self):
		self.ov.image.paste(CLEAR)
		
		self.draw_ov.line([self.draw_start_point, self.draw_point], self.col_ov)
		self.ov.pil2tex()
	
	# ---:
	
	def get_draw_point(self, touch):
		bg_x, bg_y = self.img_bg.position
		x = int((touch.location.x - bg_x) // self.zoom)
		y = int((bg_y - touch.location.y) // self.zoom)
		return Pixel(x, y)
	
	# ---:
	
	def touch_began(self, touch):
		if self.wait:
			return
		
		t_length = len(self.touches)
		
		if t_length == 1:
			ButtonNode.detect_began(touch)
			pushed = Gui.detect_began(touch)
			if pushed:
				self.mode = MODE_GUI
				self.touch_id = touch.touch_id
			
			elif self.tool is TOOL_MOVE:
				self.mode = MODE_MOVE
				self.touch_id = touch.touch_id
				self.move_start = touch.location - self.move
				self.touch_x, self.touch_y = touch.location
			
			elif touch.location in self.img_bg.frame:
				self.mode = MODE_DRAW
				self.touch_id = touch.touch_id
				p = self.get_draw_point(touch)
				self.draw_start_point = p
				self.draw_point = p
		
		elif t_length == 2 and (self.tool is not TOOL_MOVE):
			Gui.detect_ended(touch)
			self.mode = MODE_MOVE
			self.touch_id = touch.touch_id
			self.move_start = touch.location - self.move
			self.touch_x, self.touch_y = touch.location
	
	def touch_moved(self, touch):
		if self.wait:
			return
		
		if touch.touch_id == self.touch_id:
			
			if self.mode is MODE_GUI:
				Gui.detect_moved(touch)
			
			elif self.mode is MODE_MOVE:
				self.move = touch.location - self.move_start
				self.set_pos()
				x = touch.location.x - self.touch_x
				y = touch.location.y - self.touch_y + self.size.h
				self.grid.position = (x, y)
			
			elif self.mode is MODE_DRAW:
				self.draw_point = self.get_draw_point(touch)
	
	def touch_ended(self, touch):
		if self.wait:
			return
		
		t_length = len(self.touches)
		
		ButtonNode.detect_ended(touch)
		
		if t_length > 0:
			self.touches = {}
			return
		
		elif self.mode is MODE_GUI and touch.touch_id == self.touch_id:
			Gui.detect_ended(touch)
		
		elif self.mode is MODE_DRAW:
			cul = self.current_layer()
			
			if self.tool is TOOL_PICKER:
				if self.auto_tool:
					self.select_tool(self.tool_prev)
			
			elif self.tool is TOOL_CAP and self.cap_stage in {0, 2}:
				self.copy_and_paste()
				
				if self.cap_stage == 0:
					x0, y0 = self.draw_start_point
					x1, y1 = self.draw_point
					min_x = min(x0, x1)
					max_x = max(x0, x1) + 1
					min_y = min(y0, y1)
					max_y = max(y0, y1) + 1
						
					sz = (max_x - min_x, max_y - min_y)
					data = (min_x, min_y, max_x, max_y)
					
					self.cap_img_p = cul.image.transform(sz, Image.EXTENT, data)
					
					img = Image.new("RGBA", self.cap_img_p.size, CLEAR)
					draw_img = ImageDraw.Draw(img)
					w, h = img.size
					draw_img.rectangle([0, 0, w - 1, h - 1], outline=self.col_c)
					self.cap_img_s = Image.alpha_composite(self.cap_img_p, img)
					
					self.cap_point = Pixel(min_x, min_y)
					
					self.cap_stage = 1
					self.gui_cap.change_texture('files/gui/tool_cap_empty.png')
					
				else:
					self.cap_point = self.draw_point - Pixel._make(self.cap_img_p.size) // 2
					
					self.cap_stage = 3
				
			else:
				rgba = cul.image.copy()
				
				if self.tool is TOOL_CAP:
					move = self.draw_start_point - self.draw_point
					box = tuple(self.cap_point - move)
					self.ov.image.paste(CLEAR)
					self.ov.image.paste(self.cap_img_p, box)
					
					if self.cap_stage == 1:
						if self.cap_cut:
							box = (*self.cap_point, *(self.cap_point + self.cap_img_p.size))
							rgba.paste(CLEAR, box)
						self.cap_stage = 0
						self.copy_or_cut()
					else:
						self.cap_stage = 2
				
				if self.tool is TOOL_ERASER:
					rgba.paste(CLEAR, (0, 0), self.ov.image)
				else:
					rgba = Image.alpha_composite(rgba, self.ov.image)
				
				if self.undo_save("sub", cul.image, rgba, self.cur_key):
					cul.image = rgba
					cul.pil2tex()
					self.selector_img(self.cur_key)
		
		self.draw_prev_point = Pixel(-5, -5)
		
		if self.tool is not TOOL_MOVE and self.cap_stage in {0, 2}:
			self.ov.image.paste(CLEAR)
			self.ov.pil2tex()
		
		self.set_grid()
		self.mode = MODE_DEFAULT
	
	# ---:
	
	def close_view(self, sender):
		self.view.remove_subview(sender.superview)
	
	def add_view(self, v, y=0):
		sw, sh = self.size
		_, _, vw, vh = v.frame
		v.frame = ((sw - vw) / 2, (sh - vh) / 2 - y, vw, vh)
		v.corner_radius = 10
		v.border_color = '#6699cc'
		v.border_width = 3
		self.view.add_subview(v)
	
	# ---:
	
	def bt_undo(self, bt):
		if self.undo_index + 1:
			self.sound_effect('ui:switch8')
			self.undo_load(False)
			self.gui_redo.normal_color = WHITE
			if self.undo_index == -1:
				self.gui_undo.normal_color = LIGHT_GRAY
	
	def bt_redo(self, bt):
		length = len(self.undo_list)
		if self.undo_index + 1 < length:
			self.sound_effect('ui:switch9')
			self.undo_load(True)
			self.gui_undo.normal_color = WHITE
			if self.undo_index + 1 == length:
				self.gui_redo.normal_color = LIGHT_GRAY
	
	def undo_save(self, type, img1, img2, key):
		if np.array_equal(np.array(img1), np.array(img2)):
			return False
		
		undo = UndoData(type)
		undo.key = key
		if type == "sub":
			img3 = ImageChops.subtract_modulo(img1, img2)
			undo.image = img3
		else:
			undo.image = (img1, img2)
		self.undo_list[self.undo_index + 1:] = [undo]
		
		length = len(self.undo_list)
		if length > self.undo_limit:
			count = length - self.undo_limit
			del self.undo_list[:count]
		self.undo_index = min(self.undo_limit - 1, self.undo_index + 1)
		
		self.gui_undo.normal_color = WHITE
		self.gui_redo.normal_color = LIGHT_GRAY
		return True
	
	def undo_load(self, redo=False):
		length = len(self.layers)
		
		if redo:
			self.undo_index += 1
			undo = self.undo_list[self.undo_index]
		else:
			undo = self.undo_list[self.undo_index]
			self.undo_index -= 1
		
		if undo.type == "sub":
			lay = self.layers[undo.key]
			if redo:
				lay.image = ImageChops.subtract_modulo(lay.image, undo.image)
			else:
				lay.image = ImageChops.add_modulo(lay.image, undo.image)
			lay.pil2tex()
			self.selector_img(undo.key)
		
		elif undo.type == "image":
			lay = self.layers[undo.key]
			if redo:
				lay.image = undo.image[1]
			else:
				lay.image = undo.image[0]
			if undo.key == self.cur_key:
				self.new_image(lay)
			else:
				lay.pil2tex()
				self.selector_img(undo.key)
		
		elif (undo.type == "add_layer") ^ redo:
			prev_number = self.layers[undo.key].number
			self.layers[undo.key].node.remove_from_parent()
			del self.layers[undo.key]
			if undo.type == "add_layer":
				self.next_key = undo.key
				
			if self.cur_key == undo.key:
				if prev_number == 0:
					next_number = prev_number + 1
				else:
					next_number = prev_number - 1
			else:
				next_number = None
			
			for key, lay in self.layers.items():
				if lay.number == next_number:
					self.cur_key = key
					self.ov.node.z_position = lay.number + 0.5
					self.new_image(lay)
					
				if lay.number >= prev_number:
					lay.number -= 1
					lay.node.z_position = lay.number
			self.selector_remove(undo.key)
			
		else:
			if undo.type == "add_layer":
				lay = Layer(undo.image, length)
				key = self.next_key
			else:
				lay = Layer(undo.image, undo.number)
				key = undo.key
			
			for lay2 in self.layers.values():
				if lay2.number >= lay.number:
					lay2.number += 1
					lay2.node.z_position = lay2.number
			self.next_key = max(self.next_key, key + 1)
				
			self.img_bg.add_child(lay.node)
			self.layers[key] = lay
			self.selector_add(key)
	
	# ---:
	
	def bt_open(self, bt):
		self.wait = True
		v = ui.load_view('files/open.pyui')
		self.img = None
		
		for number in (1, 2, 3):
			img = ui.Image.named(f'files/save_{number}.png')
			if img:
				v[f'img_load{number}'].image = img
			else:
				v[f'bt_load{number}'].enabled = False
		
		self.add_view(v)
		v.wait_modal()
		
		if self.img:
			img = self.img.convert('RGBA')
			if not isinstance(self.img, GifImagePlugin.GifImageFile):
				self.img = None
			
			if img.size[0] * img.size[1] > 409600 and self.display_alert:
				c = dialogs.alert("Warning", "%sx%s" % img.size, "Open")
				if not c == 1:
					self.wait = False
					del self.img
					return
			
			cul = self.current_layer()
			if self.undo_save("image", cul.image, img, self.cur_key):
				cul.image = img
				self.new_image(cul)
			
			if self.img is not None:
				for index in range(1, self.img.n_frames):
					self.img.seek(index)
					self.open_add(self.img.convert('RGBA'), cul.number + index)
		
		del self.img
		self.wait = False
	
	def open_load(self, sender):
		number = int(sender.name[-1])
		self.img = Image.open(f'files/save_{number}.png')
		self.close_view(sender)
	
	def open_files(self, sender):
		c = dialogs.alert("Confirm", "", "Open")
		if c == 0:
			return
		path = dialogs.pick_document(types=['public.image'])
		try:
			self.img = Image.open(path)
		except AttributeError:
			return
		self.close_view(sender)
	
	def open_clipboard(self, sender):
		img = clipboard.get_image()
		if not isinstance(img, Image.Image):
			return
		self.img = img
		self.close_view(sender)
	
	def open_add(self, img, number):
		undo = UndoData("add_layer")
		undo.key = self.next_key
		undo.image = img.copy()
		self.undo_index += 1
		self.undo_list[self.undo_index:] = [undo]
		
		lay = Layer(img, number)
		key = self.next_key
		self.next_key += 1
		
		for key2, lay2 in self.layers.items():
			if lay.number <= lay2.number:
				lay2.number += 1
				lay2.node.z_position = lay2.number
			
		self.layers[key] = lay
		self.img_bg.add_child(lay.node)
		self.selector_add(key)
	
	# ---:
	
	def bt_download(self, bt):
		self.wait = True
		v = ui.load_view('files/download.pyui')
		self.img = self.current_layer().image
		
		for number in (1, 2, 3):
			img = ui.Image.named(f'files/save_{number}.png')
			if img:
				v[f'img_save{number}'].image = img
		
		self.add_view(v)
		v.wait_modal()
		
		del self.img
		self.wait = False
	
	def download_save(self, sender):
		number = int(sender.name[-1])
		self.img.save(f'files/save_{number}.png', format='png')
		sender.superview[f'img_save{number}'].image = pil2ui(self.img)
	
	def download_share(self, sender):
		dialogs.share_image(self.img)
	
	def download_clipboard(self, sender):
		clipboard.set_image(self.img)
		sender.title = "  copied   "
	
	def download_gif(self, sender):
		try:
			time = float(dialogs.input_alert('duration(s)', '', '0.2'))
		except ValueError:
			pass
		else:
			cul = self.current_layer()
			frames = [lay.image.convert('RGBA') for lay in sorted(
				self.layers.values(), key=lambda lay: lay.number
				) if lay.image.size == cul.image.size]
			sc_gif(frames, time)
	
	# ---:
	
	def bt_resize(self, bt):
		self.wait = True
		v = ui.load_view('files/resize.pyui')
		cul = self.current_layer()
		self.img = cul.image
		self.resize_mode = 'Resize'
		self.split_reverse = False
		
		w, h = self.img.size
		v['tx_w'].text = str(w)
		v['tx_h'].text = str(h)
		
		self.add_view(v)
		v.wait_modal()
		
		if isinstance(self.img, Image.Image):
			img = self.img
		else:
			if self.split_reverse:
				self.img.reverse()
			img = self.img[0]
		
		if self.undo_save("image", cul.image, img, self.cur_key):
			cul.image = img
			self.new_image(cul)
		
		if isinstance(self.img, list):
			for index in range(1, len(self.img)):
				self.open_add(self.img[index], cul.number + index)
		
		del self.img, self.resize_mode, self.split_reverse
		self.wait = False
	
	def resize_change(self, sender):
		if sender.name == 'bt_mode':
			if self.resize_mode == 'Resize':
				self.resize_mode = 'SplitX'
				sender.border_color = '#cc3333'
			elif self.resize_mode == 'SplitX':
				self.resize_mode = 'SplitY'
				sender.border_color = '#33cc33'
			else:
				self.resize_mode = 'Resize'
				sender.border_color = '#000000'
				title = 'Resize'
			sender.title = f'mode: {self.resize_mode}'
		else:
			if self.split_reverse:
				sender.title = 'reverse: OFF'
			else:
				sender.title = 'reverse: ON'
			self.split_reverse = not self.split_reverse
	
	def resize_ok(self, sender):
		v = sender.superview
		try:
			x = int(v['tx_x'].text)
			y = int(v['tx_y'].text)
			w = int(v['tx_w'].text)
			h = int(v['tx_h'].text)
			if w < 1 or h < 1:
				raise ValueError
		except ValueError:
			v['lb_error'].alpha = 1
			return
		
		# リサイズ
		if self.resize_mode == 'Resize':
			self.img = self.img.transform((w, h), Image.EXTENT, (x, y, w + x, h + y))
		
		# 分割
		else:
			img = self.img
			self.img = []
			
			if self.resize_mode == 'SplitX':
				div, mod = divmod(img.size[0] - x, w)
				for i in range(div):
					self.img.append(img.transform((w, h), Image.EXTENT, (
						w * i + x,
						y,
						w * (i + 1) + x,
						h + y
					)))
				if mod:
					self.img.append(img.transform((mod, h), Image.EXTENT, (
						w * div + x,
						y,
						w * div + mod + x,
						h + y
					)))
			
			else:
				div, mod = divmod(img.size[1] - y, h)
				for i in range(div):
					self.img.append(img.transform((w, h), Image.EXTENT, (
						x,
						h * i + y,
						w + x,
						h * (i + 1) + y
					)))
				if mod:
					self.img.append(img.transform((w, mod), Image.EXTENT, (
						x,
						h * div + y,
						w + x,
						h * div + mod + y
					)))
			
		self.close_view(sender)
	
	# ---:
	
	def bt_clear(self, bt):
		cul = self.current_layer()
		img = Image.new("RGBA", cul.image.size, CLEAR)
		if self.undo_save("sub", cul.image, img, self.cur_key):
			self.sound_effect('ui:rollover3')
			cul.image = img
			cul.pil2tex()
			self.selector_img(self.cur_key)
	
	def bt_zoom_in(self, bt):
		if self.zoom != 128:
			self.move *= 2
		self.zoom = min(128, self.zoom * 2)
		if self.zoom == 128:
			self.gui_zoom_in.normal_color = LIGHT_GRAY
		else:
			self.gui_zoom_out.normal_color = WHITE
		self.img_bg.scale = self.zoom
		self.set_pos()
		self.set_grid()
	
	def bt_zoom_out(self, bt):
		if self.zoom != 1:
			self.move /= 2
		self.zoom = max(1, self.zoom // 2)
		if self.zoom == 1:
			self.gui_zoom_out.normal_color = LIGHT_GRAY
		else:
			self.gui_zoom_in.normal_color = WHITE
		self.img_bg.scale = self.zoom
		self.set_pos()
		self.set_grid()
	
	# ---:
	
	def bt_option(self, bt):
		self.wait = True
		v = ui.load_view('files/option.pyui')
		
		v['lb_time'].text = datetime.datetime.now().strftime('%H : %M')
		v['lb_name'].text = f'Name: {self.folder_name}'
		
		v['tx_bgc'].text = self.bg_color
		v['bt_bgc'].background_color = self.bg_color
		v['seg_ct'].selected_index = self.color_type
		v['tx_dg'].text = "x".join(str(x) for x in self.grid_size)
		v['sw_dg'].value = self.display_grid
		
		v['sw_da'].value = self.display_alert
		v['sw_at'].value = self.auto_tool
		v['sw_ps'].value = self.play_sound
		
		self.add_view(v)
		v.wait_modal()
		
		try:
			ImageColor.getrgb(v['tx_bgc'].text)
		except ValueError:
			pass
		else:
			self.bg_color = v['tx_bgc'].text
			self.img_bg.color = self.bg_color
			self.grid_color()
		
		try:
			grid_size = v['tx_dg'].text.replace(":", "x")
			grid_size = tuple(int(v) for v in grid_size.split("x", 1))
			if len(grid_size) == 1:
				grid_size *= 2
		except ValueError:
			pass
		else:
			self.grid_size = grid_size
		
		self.color_type = v['seg_ct'].selected_index
		self.display_grid = v['sw_dg'].value
		self.display_alert = v['sw_da'].value
		self.auto_tool = v['sw_at'].value
		self.play_sound = v['sw_ps'].value
		
		if (not self.display_grid) or all(v < 0 for v in self.grid_size):
			self.grid.alpha = 0
		else:
			self.grid.alpha = 1
			self.set_grid()
		
		self.wait = False
	
	def option_bgc(self, sender):
		v = sender.superview
		try:
			color = ImageColor.getrgb(v['tx_bgc'].text)
		except ValueError:
			return
		if sender.name[:2] == 'bt':
			self.color_type = v['seg_ct'].selected_index
			sender.enabled = False
			color = self.change_color(color)
			sender.enabled = True
			v['tx_bgc'].text = '#%.2X%.2X%.2X' % color
		v['bt_bgc'].background_color = v['tx_bgc'].text
	
	# ---:
	
	def bt_center(self, bt):
		self.move = Vector2()
		self.set_pos()
		self.set_grid()
	
	def bt_bg_invert(self, bt):
		self.sound_effect('ui:switch10')
		self.img_bg.color = tuple(1 - v for v in self.img_bg.color[0:3])
		col = tuple(self.f2i(v) for v in self.img_bg.color[0:3])
		self.bg_color = '#%.2X%.2X%.2X' % col
		self.grid_color()
	
	# ---:
	
	def bt_layer_edit(self, bt):
		self.wait = True
		self.v = ui.load_view('files/layer_edit.pyui')
		
		for key, lay in self.layers.items():
			self.layer_edit_add_view(key, lay)
		
		self.add_view(self.v)
		self.v.wait_modal()
		
		if self.undo_index == -1:
			self.gui_undo.normal_color = LIGHT_GRAY
		else:
			self.gui_undo.normal_color = WHITE
		
		if self.undo_index + 1 == len(self.undo_list):
			self.gui_redo.normal_color = LIGHT_GRAY
		else:
			self.gui_redo.normal_color = WHITE
		
		for key, lay in self.layers.items():
			if key == self.cur_key:
				self.new_image(lay)
				self.ov.node.z_position = lay.node.z_position + 0.5
			else:
				lay.pil2tex()
				self.selector_img(key)
		self.selector_update()
		
		del self.v
		self.wait = False
	
	def layer_edit_add_view(self, key, lay):
		length = len(self.layers)
		scroll = self.v['scroll']
		scroll.content_size = (360, max(360, length * 80 + 20))
		ui_img = pil2ui(lay.image)
		
		y = (length - 1 - lay.number) * 80 + 20
		
		img_v = ui.ImageView()
		img_v.frame = (8, y, 64, 64)
		img_v.border_width = 1
		img_v.name = f"img_{key}"
		img_v.content_mode = ui.CONTENT_SCALE_ASPECT_FIT
		img_v.image = ui_img
		scroll.add_subview(img_v)
		
		bt_v = ui.Button()
		bt_v.frame = (80, y, 128, 64)
		bt_v.name = f"layer_{key}"
		bt_v.title = f"layer {key}"
		if key == self.cur_key:
			bt_v.border_width = 3
			bt_v.border_color = '#77ff55'
		else:
			bt_v.border_width = 1
			bt_v.action = self.layer_edit_select
		scroll.add_subview(bt_v)
		
		al_v = ui.Button()
		al_v.frame = (216, y, 64, 64)
		al_v.border_width = 1
		al_v.name = f"alpha_{key}"
		al_v.title = str(lay.node.alpha)
		al_v.action = self.layer_edit_alpha
		scroll.add_subview(al_v)
		
		up_v = ui.Button()
		up_v.frame = (288, y, 64, 64)
		up_v.border_width = 1
		up_v.name = f"up_{key}"
		up_v.image = ui.Image.named('iob:ios7_arrow_up_32')
		up_v.action = self.layer_edit_move
		scroll.add_subview(up_v)
		
		if scroll.background_color == (0, 0, 0, 1):
			img_v.border_color = 'white'
			bt_v.border_color = 'white'
			al_v.border_color = 'white'
			up_v.border_color = 'white'
	
	def layer_edit_img(self, key):
		lay = self.layers[key]
		ui_img = pil2ui(lay.image)
		img_v = self.v['scroll'][f"img_{key}"]
		img_v.image = ui_img
	
	def layer_edit_pos(self, key, y):
		scroll = self.v['scroll']
		img_v = scroll[f'img_{key}']
		bt_v = scroll[f'layer_{key}']
		al_v = scroll[f'alpha_{key}']
		up_v = scroll[f'up_{key}']
		img_v.frame = (8, y, 64, 64)
		bt_v.frame = (80, y, 128, 64)
		al_v.frame = (216, y, 64, 64)
		up_v.frame = (288, y, 64, 64)
	
	def layer_edit_select(self, sender):
		bt_prev = self.v['scroll'][f'layer_{self.cur_key}']
		self.cur_key = int(sender.name.split("_")[1])
		bt_prev.action = self.layer_edit_select
		bt_prev.border_width = 1
		bt_prev.border_color = '#000000'
		sender.action = None
		sender.border_width = 3
		sender.border_color = '#77ff55'
	
	def layer_edit_alpha(self, sender):
		key = int(sender.name.split("_")[1])
		lay = self.layers[key]
		lay.node.alpha = (lay.node.alpha + 0.5) % 1.5
		sender.title = str(lay.node.alpha)
		self.selector_alpha(key)
		
	def layer_edit_move(self, sender):
		length = len(self.layers)
		key = int(sender.name.split("_")[1])
		prev_number = self.layers[key].number
		
		if (prev_number + 1) == length:
			return
		next_number = prev_number + 1
		
		for key2, lay2 in self.layers.items():
			if lay2.number in {next_number, prev_number}:
				if key2 == key:
					lay2.number += 1
				else:
					lay2.number -= 1
				lay2.node.z_position = lay2.number
				y = (length - 1 - lay2.number) * 80 + 20
				self.layer_edit_pos(key2, y)
		self.selector_update()
	
	def layer_edit_add(self, sender, undo=None):
		length = len(self.layers)
		if undo:
			if undo.type == "add_layer":
				lay = Layer(undo.image, length)
				key = self.next_key
			else:
				lay = Layer(undo.image, undo.number)
				key = undo.key
		else:
			cul = self.current_layer()
			if sender.name == 'bt_add':
				text = "%sx%s" % cul.image.size
				text = dialogs.input_alert("image size", "W x H", text)
				if text is None:
					return
				text = text.replace(':', 'x')
				if "x" in text:
					split_text = text.split("x")
					try:
						w, h = [int(i) for i in split_text]
					except ValueError:
						return
				else:
					try:
						w = int(text)
						h = w
					except ValueError:
						return
				img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
			
			elif sender.name == 'bt_copy':
				img = cul.image.copy()
			
			else:
				sender.enabled = False
				img = self.connect()
				sender.enabled = True
				if img is None:
					return
			
			undo = UndoData("add_layer")
			undo.key = self.next_key
			undo.image = img.copy()
			self.undo_index += 1
			self.undo_list[self.undo_index:] = [undo]
			
			lay = Layer(img, length)
			key = self.next_key
			
		self.next_key = max(self.next_key, key + 1)
		
		for key2, lay2 in self.layers.items():
			if lay2.number >= lay.number:
				lay2.number += 1
				lay2.node.z_position = lay2.number
			y = (length - lay2.number) * 80 + 20
			self.layer_edit_pos(key2, y)
			
		self.layers[key] = lay
		self.img_bg.add_child(lay.node)
		self.layer_edit_add_view(key, lay)
		self.selector_add(key)
	
	def layer_edit_remove(self, sender, undo=None):
		length = len(self.layers)
		if length == 1:
			return
		
		if undo:
			key = undo.key
			prev_number = self.layers[undo.key].number
			self.layers[undo.key].node.remove_from_parent()
			del self.layers[undo.key]
			
			if undo.type == "add_layer":
				self.next_key = undo.key
			
		else:
			key = self.cur_key
			cul = self.current_layer()
			prev_number = cul.number
			
			undo = UndoData("remove_layer")
			undo.key = self.cur_key
			undo.number = prev_number
			undo.image = cul.image.copy()
			self.undo_index += 1
			self.undo_list[self.undo_index:] = [undo]
			
			cul.node.remove_from_parent()
			del self.layers[self.cur_key]
		
		scroll = self.v['scroll']
		img_v = scroll[f'img_{key}']
		bt_v = scroll[f'layer_{key}']
		al_v = scroll[f'alpha_{key}']
		up_v = scroll[f'up_{key}']
		scroll.remove_subview(img_v)
		scroll.remove_subview(bt_v)
		scroll.remove_subview(al_v)
		scroll.remove_subview(up_v)
		scroll.content_size = (360, max(360, (length - 1) * 80 + 20))
		
		if undo is None or self.cur_key == undo.key:
			if prev_number == 0:
				next_number = prev_number + 1
			else:
				next_number = prev_number - 1
		else:
			next_number = None
		
		for key2, lay2 in self.layers.items():
			if lay2.number == next_number:
				self.cur_key = key2
				bt_v = scroll[f'layer_{key2}']
				bt_v.action = None
				bt_v.border_width = 3
				bt_v.border_color = '#77ff55'
				
			if lay2.number > prev_number:
				lay2.number -= 1
				lay2.node.z_position = lay2.number
			else:
				y = (length - 2 - lay2.number) * 80 + 20
				self.layer_edit_pos(key2, y)
		self.selector_remove(key)
	
	def layer_edit_bgc(self, sender):
		scroll = self.v['scroll']
		if scroll.background_color == (0, 0, 0, 1):
			scroll.background_color = (1, 1, 1, 1)
			bd_color = (0, 0, 0, 1)
		else:
			scroll.background_color = (0, 0, 0, 1)
			bd_color = (1, 1, 1, 1)
		for v in scroll.subviews:
			if v.border_width == 1:
				v.border_color = bd_color
	
	def layer_edit_undo(self, sender):
		redo = sender.name == 'bt_redo'
			
		if redo:
			if self.undo_index + 1 == len(self.undo_list):
				return
			self.undo_index += 1
			undo = self.undo_list[self.undo_index]
		else:
			if self.undo_index == -1:
				return
			undo = self.undo_list[self.undo_index]
			self.undo_index -= 1
		
		if undo.type == "sub":
			lay = self.layers[undo.key]
			if redo:
				lay.image = ImageChops.subtract_modulo(lay.image, undo.image)
			else:
				lay.image = ImageChops.add_modulo(lay.image, undo.image)
			self.layer_edit_img(undo.key)
		
		elif undo.type == "image":
			lay = self.layers[undo.key]
			if redo:
				lay.image = undo.image[1]
			else:
				lay.image = undo.image[0]
			self.layer_edit_img(undo.key)
			
		elif (undo.type == "add_layer") ^ redo:
			self.layer_edit_remove(sender, undo)
			
		else:
			self.layer_edit_add(sender, undo)
	
	# ---:
	
	def connect(self):
		v = ui.load_view('files/connect.pyui')
		self.img = None
		self.connect_mode = 'Z'
		self.connect_reverse = False
		length = len(self.layers)
		scroll = v['scroll']
		scroll.content_size = (240, max(320, length * 80))
		
		if self.v['scroll'].background_color == (0, 0, 0, 1):
			v.background_color = (0.0, 0.0, 0.0, 1.0)
			bd_color = (1.0, 1.0, 1.0, 1.0)
			v['image'].border_color = bd_color
			v['bt_reverse'].border_color = bd_color
			scroll.border_color = bd_color
		else:
			bd_color = (0.0, 0.0, 0.0, 1.0)
		
		self.img_list = list(range(length))
		for lay in self.layers.values():
			self.img_list[lay.number] = [lay.image, False]
			
			ui_img = pil2ui(lay.image)
			
			y = (length - 1 - lay.number) * 80 + 8
			
			img_v = ui.ImageView()
			img_v.frame = (16, y, 64, 64)
			img_v.border_color = bd_color
			img_v.border_width = 1
			img_v.name = f"img_{lay.number}"
			img_v.content_mode = ui.CONTENT_SCALE_ASPECT_FIT
			img_v.image = ui_img
			scroll.add_subview(img_v)
			
			y += 8
			
			tg_v = ui.Button()
			tg_v.frame = (96, y, 48, 48)
			tg_v.border_color = bd_color
			tg_v.border_width = 1
			tg_v.name = f"toggle_{lay.number}"
			tg_v.image = ui.Image.named('iob:ios7_close_outline_24')
			tg_v.action = self.connect_toggle
			scroll.add_subview(tg_v)
			
			if (lay.number + 1) != length:
				up_v = ui.Button()
				up_v.frame = (160, y, 48, 48)
				up_v.border_color = bd_color
				up_v.border_width = 1
				up_v.name = f"up_{lay.number}"
				up_v.image = ui.Image.named('iob:arrow_up_b_24')
				up_v.action = self.connect_move
				scroll.add_subview(up_v)
		
		self.connect_update(scroll)
		
		self.add_view(v)
		v.wait_modal()
		
		img = self.img
		del self.img_list, self.img, self.connect_mode, self.connect_reverse
		return img
	
	def connect_update(self, sender):
		selected = []
		w = 0
		h = 0
		view = sender.superview['image']
		
		for img, on in self.img_list:
			if on:
				selected.append(img)
				if self.connect_mode == 'X':
					w += img.size[0]
					h = max(h, img.size[1])
				elif self.connect_mode == 'Y':
					w = max(w, img.size[0])
					h += img.size[1]
				else:
					w = max(w, img.size[0])
					h = max(h, img.size[1])
		length = len(selected)
		if self.connect_reverse:
			selected.reverse()
		
		if not length:
			self.img = None
			view.image = None
			return
		elif length == 1:
			self.img = selected[0]
		elif self.connect_mode == 'X':
			self.img = self.connect_x(w, h, selected)
		elif self.connect_mode == 'Y':
			self.img = self.connect_y(w, h, selected)
		else:
			self.img = self.connect_z(w, h, selected)
		
		w, h = self.img.size
		max_size = max(w, h)
		w = w / max_size * 160
		h = h / max_size * 160
		x = 360 - w / 2
		y = 120 - h / 2
		view.frame = (x, y, w, h)
			
		ui_img = pil2ui(self.img)
		view.image = ui_img
	
	def connect_x(self, w, h, selected):
		dst = Image.new("RGBA", (w, h), CLEAR)
		x = 0
		for src in selected:
			dst.paste(src, (x, 0))
			x += src.size[0]
		return dst
		
	def connect_y(self, w, h, selected):
		dst = Image.new("RGBA", (w, h), CLEAR)
		y = 0
		for src in selected:
			dst.paste(src, (0, y))
			y += src.size[1]
		return dst
		
	def connect_z(self, w, h, selected):
		dst = selected[0]
		if dst.size != (w, h):
			dst = dst.transform((w, h), Image.EXTENT, (0, 0, w, h))
		for src in selected[1:]:
			if src.size != (w, h):
				src = src.transform((w, h), Image.EXTENT, (0, 0, w, h))
			dst = Image.alpha_composite(dst, src)
		return dst
	
	def connect_change(self, sender):
		if sender.name == 'bt_mode':
			if self.connect_mode == 'X':
				self.connect_mode = 'Y'
				sender.border_color = '#33cc33'
			elif self.connect_mode == 'Y':
				self.connect_mode = 'Z'
				sender.border_color = '#3333cc'
			else:
				self.connect_mode = 'X'
				sender.border_color = '#cc3333'
			sender.title = f'mode: {self.connect_mode}'
		elif sender.name == 'bt_reverse':
			if self.connect_reverse:
				sender.title = 'reverse: OFF'
			else:
				sender.title = 'reverse: ON'
			self.connect_reverse = not self.connect_reverse
		self.connect_update(sender)
	
	def connect_toggle(self, sender, change=True):
		number = int(sender.name.split("_")[1])
		if change:
			self.img_list[number][1] = not self.img_list[number][1]
			self.connect_update(sender.superview)
		if self.img_list[number][1]:
			sender.image = ui.Image.named('iob:ios7_checkmark_24')
		else:
			sender.image = ui.Image.named('iob:ios7_close_outline_24')
	
	def connect_move(self, sender):
		number = int(sender.name.split("_")[1])
		if (number + 1) == len(self.img_list):
			return
		src = self.img_list[number]
		dst = self.img_list[number + 1]
		self.img_list[number + 1] = src
		self.img_list[number] = dst
		
		scroll = sender.superview
		
		if src[1] ^ dst[1]:
			self.connect_toggle(scroll[f'toggle_{number}'], False)
			self.connect_toggle(scroll[f'toogle_{number + 1}'], False)
		
		img_v = scroll[f'img_{number}']
		img_v2 = scroll[f'img_{number + 1}']
		img_v.y -= 80
		img_v2.y += 80
		img_v.name = f"img_{number + 1}"
		img_v2.name = f"img_{number}"
		
		self.connect_update(scroll)
	
	# ---:
	
	def bt_palette_edit(self, bt):
		self.wait = True
		self.v = ui.load_view('files/palette_edit.pyui')
		
		self.plt = self.colors
		self.plt_key = 0
		self.plts_glb = []
		self.plts_lcl = []
		self.plt_index = [False, 0]
		
		sc_lcl = self.v['scroll_lcl']
		sc_glb = self.v['scroll_glb']
		
		sc_glb.hidden = True
		sc_glb.x = 0
		
		self.palette_edit_update_col()
		
		# ローカル0の設定
		self.plts_lcl.append(self.colors)
		img = Image.new("RGBA", (8, 1), CLEAR)
		img.putdata(list(self.colors.values()))
		img = img.transform((32, 4), Image.EXTENT, (0, 0, 8, 1))
		ui_img = pil2ui(img)
		sc_lcl['img_0'].image = ui_img
		
		# ファイルロード
		KEYS = [0, 1, 2, 3, 4, 5, 6, 7]
		sample_path = 'files/sample_data/palettes.png'
		tx = ''
		
		# ローカルの読み込み
		try:
			plts_img = Image.open(f'files/save_data/{self.folder_name}/palettes.png')
		except FileNotFoundError:
			tx += '画像ファイルが見つかりません。\n'
			plts_img = Image.open(sample_path)
		
		for y in range(plts_img.size[1]):
			img = plts_img.transform((8, 1), Image.EXTENT, (0, y, 8, y))
			data = img.getdata()
			plt = dict(zip(KEYS, data))
			self.plts_lcl.append(plt)
			y += 1
			self.palette_edit_add_view(y, img, False)
		
		# グローバルの読み込み
		try:
			plts_img = Image.open(f'files/palettes.png')
		except FileNotFoundError:
			tx += '画像ファイルが見つかりません。\n'
			plts_img = Image.open(sample_path)
		
		for y in range(plts_img.size[1]):
			img = plts_img.transform((8, 1), Image.EXTENT, (0, y, 8, y))
			data = img.getdata()
			plt = dict(zip(KEYS, data))
			self.plts_glb.append(plt)
			self.palette_edit_add_view(y, img, True)
		
		if tx:
			tx += '>サンプルデータをロードしました。'
			self.new_message(tx)
		
		self.palette_edit_select_col(self.v[f'bt_col_{self.color_key}'])
		
		self.add_view(self.v)
		self.v.wait_modal()
		
		# 保存
		data = []
		for plt in self.plts_lcl[1:]:
			data.extend(list(plt.values()))
		img = Image.new("RGBA", (8, len(self.plts_lcl) - 1), CLEAR)
		img.putdata(data)
		img.save(f'files/save_data/{self.folder_name}/palettes.png')
		
		data.clear()
		for plt in self.plts_glb:
			data.extend(list(plt.values()))
		img = Image.new("RGBA", (8, len(self.plts_glb)), CLEAR)
		img.putdata(data)
		img.save('files/palettes.png')
		
		self.set_palette(self.plt)
		
		del self.v, self.plt, self.plt_key
		del self.plts_glb, self.plts_lcl, self.plt_index
		self.wait = False
	
	def palette_edit_add_view(self, index, img, glb):
		img = img.transform((32, 4), Image.EXTENT, (0, 0, 8, 1))
		ui_img = pil2ui(img)
		
		select_img = ui.Image.named('iob:ios7_checkmark_outline_24')
		delete_img = ui.Image.named('iob:trash_a_24')
		up_img = ui.Image.named('iob:arrow_up_b_24')
		
		y = index * 128 + 8
		
		if glb:
			scroll = self.v['scroll_glb']
			plts = self.plts_glb
			number = index
		else:
			scroll = self.v['scroll_lcl']
			plts = self.plts_lcl
			number = index - 1
			
		scroll.content_size = (320, max(320, len(plts) * 128))
		
		img_v = ui.ImageView()
		img_v.frame = (16, y, 256, 32)
		img_v.border_width = 1
		img_v.name = f"img_{index}"
		img_v.image = ui_img
		scroll.add_subview(img_v)
		
		y += 40
		
		sl_v = ui.Button()
		sl_v.frame = (176, y, 96, 48)
		sl_v.border_width = 1
		sl_v.name = f"select_{index}"
		sl_v.image = select_img
		sl_v.action = self.palette_edit_select
		scroll.add_subview(sl_v)
		
		if number > 0:
			dl_v = ui.Button()
			dl_v.frame = (16, y, 64, 48)
			dl_v.border_width = 1
			dl_v.name = f"delete_{index}"
			dl_v.image = delete_img
			dl_v.action = self.palette_edit_delete
			scroll.add_subview(dl_v)
			
			up_v = ui.Button()
			up_v.frame = (96, y, 64, 48)
			up_v.border_width = 1
			up_v.name = f"up_{index}"
			up_v.image = up_img
			up_v.action = self.palette_edit_move
			scroll.add_subview(up_v)
			
			if number == 1:
				dl_v = ui.Button()
				dl_v.frame = (16, y - 128, 64, 48)
				dl_v.border_width = 1
				dl_v.name = f"delete_{index - 1}"
				dl_v.image = delete_img
				dl_v.action = self.palette_edit_delete
				scroll.add_subview(dl_v)
			
	def palette_edit_update_col(self):
		for key, val in self.plt.items():
			bt = self.v[f'bt_col_{key}']
			col = tuple(v / 255 for v in val[0:3])
			bt.background_color = col
			col = tuple(min(0.8, 1.5 - v) for v in col)
			bt.border_color = col
			if val[3] != 255:
				bt.tint_color = col
				bt.title = str(val[3])
			else:
				bt.title = None
	
	def palette_edit_select_col(self, sender):
		key = int(sender.name.split('col_')[1])
		col = self.plt[key]
		
		bt = self.v[f'bt_col_{self.plt_key}']
		bt.action = self.palette_edit_select_col
		bt.border_width = 1
		
		r, g, b, a = col
		self.v['lb_r'].text = f" R: {r}"
		self.v['lb_g'].text = f" G: {g}"
		self.v['lb_b'].text = f" B: {b}"
		self.v['lb_a'].text = f" A: {a}"
		
		hex = "#%.2X%.2X%.2X" % col[0:3]
		self.v['lb_hex'].text = hex
		
		sender.action = None
		sender.border_width = 4
		
		self.plt_key = key
	
	def palette_edit_add(self, sender):
		if self.v['scroll_lcl'].hidden:
			plts = self.plts_glb
			exists = plts
		else:
			plts = self.plts_lcl
			exists = plts[1:]
			
		if self.plt in exists:
			sender.title = "existing"
			return
		
		sender.title = "add"
		index = len(plts)
		
		img = Image.new("RGBA", (8, 1), CLEAR)
		img.putdata(list(self.plt.values()))
		plts.append(self.plt)
		
		self.palette_edit_add_view(index, img, self.v['scroll_lcl'].hidden)
	
	def palette_edit_change(self, sender):
		if self.v['scroll_lcl'].hidden:
			self.v['scroll_glb'].hidden = True
			self.v['scroll_lcl'].hidden = False
			self.v['lb_mode'].text = "mode: local"
		else:
			self.v['scroll_glb'].hidden = False
			self.v['scroll_lcl'].hidden = True
			self.v['lb_mode'].text = "mode: global"
	
	def palette_edit_select(self, sender):
		index = int(sender.name.split('_')[1])
		is_glb = sender.superview.name == 'scroll_glb'
		
		select_img = ui.Image.named('iob:ios7_checkmark_outline_24')
		selected_img = ui.Image.named('iob:ios7_checkmark_24')
		
		if is_glb:
			scroll = self.v['scroll_glb']
			plts = self.plts_glb
		else:
			scroll = self.v['scroll_lcl']
			plts = self.plts_lcl
		
		self.plt = plts[index]
		self.palette_edit_update_col()
		
		sender.action = None
		sender.image = selected_img
		if self.plt_index[0]:
			bt = self.v['scroll_glb'][f"select_{self.plt_index[1]}"]
		else:
			bt = self.v['scroll_lcl'][f"select_{self.plt_index[1]}"]
		# くそてきとうエラー対策。次作る時はちゃんと全部つくってー
		if bt:
			bt.action = self.palette_edit_select
			bt.image = select_img
		self.plt_index = [is_glb, index]
		
		bt = self.v[f"bt_col_{self.plt_key}"]
		self.palette_edit_select_col(bt)
	
	def palette_edit_delete(self, sender):
		c = dialogs.alert("Confirm", "", "Delete")
		if c == 0:
			return
		
		index = int(sender.name.split('_')[1])
		is_glb = sender.superview.name == 'scroll_glb'
		
		if is_glb:
			scroll = self.v['scroll_glb']
			plts = self.plts_glb
		else:
			scroll = self.v['scroll_lcl']
			plts = self.plts_lcl
		
		end = len(plts) - 1
		
		img_v = scroll[f'img_{index}']
		sl_v = scroll[f'select_{end}']
		dl_v = scroll[f'delete_{end}']
		scroll.remove_subview(img_v)
		scroll.remove_subview(sl_v)
		scroll.remove_subview(dl_v)
		if end > 1 or (is_glb and end > 0):
			up_v = scroll[f'up_{end}']
			scroll.remove_subview(up_v)
		if (not is_glb and end == 2) or (is_glb and end == 1):
			if is_glb:
				dl_v = scroll[f'delete_0']
			else:
				dl_v = scroll[f'delete_1']
			scroll.remove_subview(dl_v)
		
		del plts[index]
		scroll.content_size = (320, max(320, end * 128))
		
		if index == end:
			return
		for idx in range(index + 1, end + 1):
			img_v = scroll[f'img_{idx}']
			img_v.y -= 128
			img_v.name = f'img_{idx - 1}'
	
	def palette_edit_move(self, sender):
		index_src = int(sender.name.split('_')[1])
		index_dst = index_src - 1
		is_glb = sender.superview.name == 'scroll_glb'
		
		select_img = ui.Image.named('iob:ios7_checkmark_outline_24')
		selected_img = ui.Image.named('iob:ios7_checkmark_24')
		
		if is_glb:
			scroll = self.v['scroll_glb']
			plts = self.plts_glb
		else:
			scroll = self.v['scroll_lcl']
			plts = self.plts_lcl
		
		plt = plts[index_src]
		plts[index_src] = plts[index_dst]
		plts[index_dst] = plt
		
		if self.plt_index[1] == index_src:
			self.plt_index[1] -= 1
		elif self.plt_index[1] == index_dst:
			self.plt_index[1] += 1
		
		src_img_v = scroll[f'img_{index_src}']
		src_sl_v = scroll[f'select_{index_src}']
		dst_img_v = scroll[f'img_{index_dst}']
		dst_sl_v = scroll[f'select_{index_dst}']
		src_img_v.y -= 128
		src_sl_v.y -= 128
		dst_img_v.y += 128
		dst_sl_v.y += 128
		src_img_v.name = f'img_{index_dst}'
		src_sl_v.name = f'select_{index_dst}'
		dst_img_v.name = f'img_{index_src}'
		dst_sl_v.name = f'select_{index_src}'
	
	def set_palette(self, plt):
		for key, col in plt.items():
			gui_color = getattr(self, f'gui_color{key}')
			gui_color.change_color(tuple(v / 255 for v in col[0:3]))
			gui_color.set_alpha(col[3])
		
		self.colors = plt
		self.choose_color(self.color_key)
	
	# ---:
	
	def bt_anim(self, bt):
		self.wait = True
		v = ui.load_view('files/anim.pyui')
		
		alphas = {key: lay.node.alpha for key, lay in self.layers.items()}
		
		for key, lay in self.layers.items():
			lay.node.alpha = 0.0
			self.selector_alpha(key)
		
		def animation():
			cul = self.current_layer()
			lays = [lay for lay in sorted(
				self.layers.items(), key=lambda lay: lay[1].number
				) if lay[1].image.size == cul.image.size]
			del cul
			while True:
				for key, lay in lays:
					lay.node.alpha = 1.0
					self.selector_alpha(key)
					yield
					lay.node.alpha = 0.0
					self.selector_alpha(key)
				if v['switch'].value:
					for _ in range(10):
						yield
		
		self.anim = animation()
		self.anim_update(v['slider'])
		
		self.add_view(v)
		v.wait_modal()
		
		self.remove_action('anim')
		for key, a in alphas.items():
			self.layers[key].node.alpha = a
			self.selector_alpha(key)
		
		del self.anim
		self.wait = False
	
	def anim_update(self, sender):
		if sender.name == 'slider':
			t = max(sender.value * 0.5, 0.01)
			sender.superview['text'].text = f"{t:.2f}"
		else:
			try:
				t = float(sender.text)
			except ValueError:
				t = max(sender.superview['slider'].value * 0.5, 0.01)
				sender.text = f"{t:.2f}"
			else:
				sender.superview['slider'].value = t * 2
		
		act = A.repeat_forever(A.sequence(A.call(self.anim.__next__), A.wait(t)))
		self.run_action(act, 'anim')
	
	# ---:
	
	def bt_switch(self, bt):
		self.wait = True
		move = min(self.size[0] / 16, 64) * 1.5
		guis = (
			self.gui_open,
			self.gui_download,
			self.gui_resize,
			self.gui_clear,
			self.gui_zoom_in,
			self.gui_zoom_out,
			self.gui_option,
			self.gui_center,
			self.gui_bg_invert,
			self.gui_layer_edit,
			self.gui_palette_edit,
			self.gui_anim)
		
		if self.switching:
			move *= -1
		
		def animation():
			self.lay_selector.y -= move
		act = A.move_by(0, move, 0.15)
		
		self.sound_effect('ui:switch2')
		for gui in guis:
			gui.run_action(act)
		ui.animate(animation, 0.15, completion=self.switch_end)
	
	def switch_end(self):
		self.switching = not self.switching
		self.wait = False
	
	# ---:
	
	def selector_add(self, key):
		w = self.size[0]
		l = min(w / 16, 64)
		lay = self.layers[key]
		
		bt_v = ui.Button()
		bt_v.frame = (l * (4.4 + (lay.number * 1.5)), l / 4, l * 1.2, l)
		bt_v.name = f'layer_{key}'
		bt_v.border_color = 'white'
		bt_v.border_width = 1
		bt_v.action = self.selector_select
		self.lay_selector.add_subview(bt_v)
		
		img_v = ui.ImageView()
		img_v.frame = (0, 0, l * 1.2, l)
		img_v.name = f'image'
		img_v.content_mode = ui.CONTENT_SCALE_ASPECT_FIT
		img_v.image = pil2ui(lay.image)
		img_v.touch_enabled = False
		bt_v.add_subview(img_v)
		
		lb_v = ui.Label()
		lb_v.frame = (0, l * 0.6, l * 1.2, l * 0.4)
		lb_v.name = f'alpha'
		lb_v.background_color = (0, 0, 0, 0.3)
		lb_v.alignment = ui.ALIGN_CENTER
		lb_v.text_color = 'white'
		lb_v.text = str(lay.node.alpha)
		bt_v.add_subview(lb_v)
		
		self.selector_update()
	
	def selector_remove(self, key):
		bt_v = self.lay_selector[f'layer_{key}']
		self.lay_selector.remove_subview(bt_v)
		self.selector_update()
	
	def selector_img(self, key):
		img_v = self.lay_selector[f'layer_{key}']['image']
		lay = self.layers[key]
		ui_img = pil2ui(lay.image)
		img_v.image = ui_img
	
	def selector_alpha(self, key):
		lb_v = self.lay_selector[f'layer_{key}']['alpha']
		lay = self.layers[key]
		lb_v.text = str(lay.node.alpha)
	
	def selector_update(self):
		w = self.size[0]
		l = min(w / 16, 64)
		self.lay_selector.content_size = (
			l * max(10, len(self.layers) * 1.5 + 8.5), l * 1.5)
		for bt_v in self.lay_selector.subviews:
			key = int(bt_v.name.split("_")[1])
			lay = self.layers[key]
			if key == self.cur_key:
				bt_v.border_color = '#77ff55'
				bt_v.border_width = 3
			else:
				bt_v.border_color = 'white'
				bt_v.border_width = 1
			bt_v.x = l * (4.4 + (lay.number * 1.5))
	
	def selector_select(self, sender):
		if self.mode is MODE_DEFAULT:
			key = int(sender.name.split("_")[1])
			if key == self.cur_key:
				lay = self.layers[key]
				lay.node.alpha = (lay.node.alpha + 0.5) % 1.5
				sender['alpha'].text = str(lay.node.alpha)
			
			else:
				bt_v = self.lay_selector[f'layer_{self.cur_key}']
				bt_v.border_color = 'white'
				bt_v.border_width = 1
				sender.border_color = '#77ff55'
				sender.border_width = 3
				self.cur_key = key
				cul = self.current_layer()
				self.new_image(cul)
				self.ov.node.z_position = cul.node.z_position + 0.5
	
	# ---:
	
	def bt_color(self, bt):
		key = bt.key
		self.choose_color(key)
	
	def choose_color(self, key):
		self.color_key = key
		
		self.col_ov = self.colors[key]
		a = self.col_ov[3]
		r, g, b = (v * a // 255 for v in self.col_ov[0:3])
		self.col_c = (r, g, b, 128)
		
		w, h = self.size
		m = min(h / 16, 48)
		mh = m / 2
		self.gui_color_frame.position = (w - mh, h - m * (5 + key))
		
		col = tuple(min(1, 1.75 - v / 255) for v in self.col_ov[0:3])
		self.gui_color_frame.stroke_color = col
	
	def bt_color_change(self, bt):
		self.wait = True
		color = self.colors[self.color_key]
		color = self.change_color(color)
		
		gui_color = getattr(self, f'gui_color{self.color_key}')
		gui_color.change_color(tuple(v / 255 for v in color[0:3]))
		gui_color.set_alpha(color[3])
		
		self.colors[self.color_key] = color
		self.choose_color(self.color_key)
		self.wait = False
	
	def change_color(self, color):
		if self.color_type == 0:
			color = self.col_select(color)
		
		elif self.color_type == 1:
			color = self.col_mixer(color)
		
		elif self.color_type == 2:
			color = self.col_picker(color)
		
		return color
	
	# ---:
	
	def col_select(self, color):
		v = ui.load_view('files/colorselect.pyui')
		self.select_color = color
		
		if len(color) == 3:
			v['lb_alpha'].hidden = True
			v['tx_alpha'].hidden = True
		self.col_select_update(v['v_color'])
		
		self.add_view(v)
		v.wait_modal()
		
		if self.select_color is not None:
			color = self.select_color
		del self.select_color
		return color
	
	def col_select_cancel(self, sender):
		self.select_color = None
		self.close_view(sender)
	
	def col_select_update(self, sender):
		v = sender.superview
		col = self.select_color[0:3]
		v['v_color'].background_color = tuple(c / 255 for c in col)
		v['lb_color'].text = '#%.2X%.2X%.2X' % col
		if len(self.select_color) == 4:
			alpha = self.select_color[3]
			v['v_color'].alpha = alpha / 255
			v['lb_alpha'].text = f"{alpha/255:.2%}"
			v['tx_alpha'].text = str(alpha)
	
	def col_select_picker(self, sender):
		sender.enabled = False
		color = self.col_picker(self.select_color)
		sender.enabled = True
		self.select_color = color
		self.col_select_update(sender)
	
	def col_select_mixer(self, sender):
		sender.enabled = False
		color = self.col_mixer(self.select_color)
		sender.enabled = True
		self.select_color = color
		self.col_select_update(sender)
	
	def col_select_text(self, sender):
		v = sender.superview
		alpha = self.select_color[3]
		try:
			alpha = max(0, min(255, int(sender.text.split("%")[0])))
		except ValueError:
			v['lb_error'].alpha = 1
			v['tx_alpha'].text = str(alpha)
		else:
			self.select_color = (*self.select_color[0:3], alpha)
			v['v_color'].alpha = alpha / 255
			v['lb_alpha'].text = f"{alpha/255:.2%}"
			v['lb_error'].alpha = 0
	
	# ---:
	
	def col_picker(self, color):
		v = ui.load_view('files/colorpicker.pyui')
		self.picker_color = color[0:3]
		
		flag = True
		for bt in v.subviews:
			if bt.name[:8] == 'bt_color':
				col = ImageColor.getrgb(bt.name[-7:])
				bt.action = self.col_picker_choose
				bt.border_color = tuple(max(0, 0.25 - c / 255) for c in col)
				if flag and col == self.picker_color:
					bt.border_width = 4
					flag = False
		
		self.add_view(v)
		v.wait_modal()
		
		if self.picker_color is not None:
			if len(color) == 4:
				color = (*self.picker_color, color[3])
			else:
				color = self.picker_color
		del self.picker_color
		return color
	
	def col_picker_cancel(self, sender):
		self.picker_color = None
		self.close_view(sender)
	
	def col_picker_choose(self, sender):
		v = sender.superview
		for bt in v.subviews:
			if bt.name[:8] == 'bt_color' and bt != sender:
				bt.border_width = 1
		sender.border_width = 4
		self.picker_color = ImageColor.getrgb(sender.name[-7:])
	
	# ---:
	
	def col_mixer(self, color):
		v = ui.load_view('files/colormixer.pyui')
		self.mixer_color = color
		
		v['sl_red'].value = color[0] / 255
		v['sl_green'].value = color[1] / 255
		v['sl_blue'].value = color[2] / 255
		
		if len(color) == 3:
			v['tx_alpha'].hidden = True
			v['sl_alpha'].hidden = True
		else:
			v['sl_alpha'].value = color[3] / 255
		self.col_mixer_slider(v['sl_red'])
		
		self.add_view(v, 16)
		v.wait_modal()
		
		if self.mixer_color is not None:
			color = tuple(self.f2i(v) for v in self.mixer_color)
		del self.mixer_color
		return color
	
	def col_mixer_cancel(self, sender):
		self.mixer_color = None
		self.close_view(sender)
	
	def col_mixer_update(self, sender):
		v = sender.superview
		r = v['sl_red'].value
		g = v['sl_green'].value
		b = v['sl_blue'].value
		if v['sl_alpha'].hidden:
			self.mixer_color = (r, g, b)
		else:
			a = v['sl_alpha'].value
			self.mixer_color = (r, g, b, a)
	
	def col_mixer_picker(self, sender):
		sender.enabled = False
		color = self.col_picker(tuple(self.f2i(v) for v in self.mixer_color[0:3]))
		sender.enabled = True
		v = sender.superview
		v['sl_red'].value = color[0] / 255
		v['sl_green'].value = color[1] / 255
		v['sl_blue'].value = color[2] / 255
		self.col_mixer_slider(v['sl_red'])
	
	def col_mixer_slider(self, sender):
		self.col_mixer_update(sender)
		v = sender.superview
		v['bt_color'].background_color = self.mixer_color[0:3]
		r, g, b = tuple(self.f2i(v) for v in self.mixer_color[0:3])
		v['tx_color'].text = '#%.2X%.2X%.2X' % (r, g, b)
		v['tx_red'].text = str(r)
		v['tx_green'].text = str(g)
		v['tx_blue'].text = str(b)
		if not v['tx_alpha'].hidden:
			v['tx_alpha'].text = str(self.f2i(self.mixer_color[3]))
			v['bt_color'].alpha = self.mixer_color[3]
	
	def col_mixer_text(self, sender):
		v = sender.superview
		is_hex = sender.name == 'tx_color'
		is_alpha = sender.name == 'tx_alpha'
		try:
			if is_hex:
				r, g, b = ImageColor.getrgb(sender.text)
			elif is_alpha:
				a = int(v['tx_alpha'].text) / 255
			else:
				r = int(v['tx_red'].text)
				g = int(v['tx_green'].text)
				b = int(v['tx_blue'].text)
		except ValueError:
			v['lb_error'].alpha = 1
		else:
			if is_alpha:
				v['sl_alpha'].value = a
			else:
				v['sl_red'].value = r / 255
				v['sl_green'].value = g / 255
				v['sl_blue'].value = b / 255
			self.col_mixer_update(sender)
			
			if is_hex:
				v['tx_red'].text = str(r)
				v['tx_green'].text = str(g)
				v['tx_blue'].text = str(b)
			elif is_alpha:
				v['bt_color'].alpha = a
			else:
				v['tx_color'].text = '#%.2X%.2X%.2X' % (r, g, b)
			
			v['bt_color'].background_color = self.mixer_color[0:3]
			v['lb_error'].alpha = 0
	
	# ---:
	
	def change_tool(self, bt):
		if self.cap_stage == 1:
			self.cap_stage = 0
			self.copy_or_cut()
		elif self.cap_stage == 3:
			self.cap_stage = 2
		
		self.tool_gui.normal_color = WHITE
		self.tool_gui = bt
		bt.normal_color = GRAY
	
	def select_pencil(self, bt):
		if self.tool is TOOL_PENCIL:
			return
		self.change_tool(bt)
		self.tool = TOOL_PENCIL
		self.draw_method = self.draw_pencil
		
	def select_eraser(self, bt):
		if self.tool is TOOL_ERASER:
			self.erase_rect = not self.erase_rect
			if self.erase_rect:
				bt.change_texture('files/gui/tool_eraser_rect.png')
			else:
				bt.change_texture('files/gui/tool_eraser.png')
			return
		self.change_tool(bt)
		self.tool = TOOL_ERASER
		self.draw_method = self.draw_eraser
	
	def select_picker(self, bt):
		if self.tool is TOOL_PICKER:
			self.pick_alpha = not self.pick_alpha
			if self.pick_alpha:
				bt.change_texture('files/gui/tool_rgba.png')
			else:
				bt.change_texture('files/gui/tool_picker.png')
			return
		else:
			self.tool_prev = self.tool
		self.change_tool(bt)
		self.tool = TOOL_PICKER
		self.draw_method = self.pick_color
	
	def select_cap(self, bt):
		if self.tool is TOOL_CAP:
			if self.cap_stage == 0:
				self.cap_cut = not self.cap_cut
				self.copy_or_cut()
			elif self.cap_stage == 1:
				self.cap_stage = 2
				bt.change_texture('files/gui/tool_cap_saved.png')
			elif self.cap_stage >= 2:
				self.cap_stage = 0
				self.copy_or_cut()
			return
		self.change_tool(bt)
		self.tool = TOOL_CAP
		self.draw_method = self.copy_and_paste
	
	def copy_or_cut(self):
		if self.cap_cut:
			self.gui_cap.change_texture('files/gui/tool_cap_cut.png')
		else:
			self.gui_cap.change_texture('files/gui/tool_cap.png')
	
	def select_fill(self, bt):
		if self.tool is TOOL_FILL:
			return
		self.change_tool(bt)
		self.tool = TOOL_FILL
		self.draw_method = self.draw_fill
	
	def select_rect(self, bt):
		if self.tool is TOOL_RECT:
			self.rect_fill = not self.rect_fill
			if self.rect_fill:
				bt.change_texture('files/gui/tool_rect.png')
			else:
				bt.change_texture('files/gui/tool_rect_outline.png')
			return
		self.change_tool(bt)
		self.tool = TOOL_RECT
		self.draw_method = self.draw_rect
	
	def select_circle(self, bt):
		if self.tool is TOOL_CIRCLE:
			self.circle_fill = not self.circle_fill
			if self.circle_fill:
				bt.change_texture('files/gui/tool_circle.png')
			else:
				bt.change_texture('files/gui/tool_circle_outline.png')
			return
		self.change_tool(bt)
		self.tool = TOOL_CIRCLE
		self.draw_method = self.draw_circle
	
	def select_line(self, bt):
		if self.tool is TOOL_LINE:
			return
		self.change_tool(bt)
		self.tool = TOOL_LINE
		self.draw_method = self.draw_line
	
	def select_move(self, bt):
		if self.tool is TOOL_MOVE:
			return
		self.change_tool(bt)
		self.tool = TOOL_MOVE
		self.draw_method = None
	
	def select_tool(self, tool):
		if tool is TOOL_PENCIL:
			self.select_pencil(self.gui_pencil)
		elif tool is TOOL_ERASER:
			self.select_eraser(self.gui_eraser)
		elif tool is TOOL_PICKER:
			self.select_picker(self.gui_picker)
		elif tool is TOOL_CAP:
			self.select_cap(self.gui_cap)
		elif tool is TOOL_FILL:
			self.select_fill(self.gui_fill)
		elif tool is TOOL_RECT:
			self.select_rect(self.gui_rect)
		elif tool is TOOL_CIRCLE:
			self.select_circle(self.gui_circle)
		elif tool is TOOL_LINE:
			self.select_line(self.gui_line)
		elif tool is TOOL_MOVE:
			self.select_move(self.gui_move)
	
	# ---:
	
	@staticmethod
	def f2i(x):
		return int((x * 510 + 1) // 2)
	
	def current_layer(self):
		return self.layers[self.cur_key]
		
	def sound_effect(self, name):
		if self.play_sound:
			sound.play_effect(name)
	
	def new_image(self, lay):
		lay.pil2tex()
		
		self.img_bg.size = lay.node.size
		self.img_bg.scale = self.zoom
		self.ov.node.size = lay.node.size
		self.set_pos()
		self.set_grid()
		self.selector_img(self.cur_key)
		if self.ov.image.size != lay.image.size:
			self.ov.image = Image.new("RGBA", lay.image.size, CLEAR)
			self.ov.pil2tex()
			self.draw_ov = ImageDraw.Draw(self.ov.image)
	
	def set_pos(self):
		w = self.img_bg.frame.w
		h = self.img_bg.frame.h
		self.img_bg.position = (
			(self.size.w - w) / 2, (self.size.h + h) / 2 + 32
		) + self.move
	
	def set_grid(self):
		grid_w, grid_h = self.grid_size
		if (grid_w < 0 and grid_h < 0) or not self.display_grid:
			return
		cul = self.current_layer()
		
		thin_path = ui.Path.rect(0, 0, 0, 0)
		thin_path.line_width = 0.15
		thick_path = ui.Path.rect(0, 0, 0, 0)
		thick_path.line_width = 0.6
		
		mag = max(1, 4 // self.zoom)  # magnification
		if grid_w < 16 or grid_h < 16:
			grid_w *= mag
			grid_h *= mag
		
		# 変更しない
		size_w, size_h = self.size
		min_x = max(0, min(size_w, self.img_bg.frame.min_x))
		max_x = max(0, min(size_w, self.img_bg.frame.max_x))
		min_y = max(0, min(size_h, size_h - self.img_bg.frame.max_y))
		max_y = max(0, min(size_h, size_h - self.img_bg.frame.min_y))
		
		if 0 <= grid_w:
			for px in range(mag, cul.image.size[0], mag):
				x = self.img_bg.position.x + self.zoom * px
				if x < 0:
					continue
				elif x > size_w:
					break
				if grid_w and not px % grid_w:
					thick_path.move_to(x, min_y)
					thick_path.line_to(x, max_y)
				else:
					thin_path.move_to(x, min_y)
					thin_path.line_to(x, max_y)
		
		if 0 <= grid_h:
			for py in range(mag, cul.image.size[1], mag):
				y = self.size.h - self.img_bg.position.y + self.zoom * py
				if y < 0:
					continue
				elif y > size_h:
					break
				if grid_h and not py % grid_h:
					thick_path.move_to(min_x, y)
					thick_path.line_to(max_x, y)
				else:
					thin_path.move_to(min_x, y)
					thin_path.line_to(max_x, y)
		
		self.grid.path = thin_path
		self.thick_grid.path = thick_path
		self.grid.position = (0, size_h)
	
	def grid_color(self):
		if sum(self.img_bg.color[0:3]) > 0.5:
			self.grid.stroke_color = BLACK
			self.thick_grid.stroke_color = BLACK
		else:
			self.grid.stroke_color = GRAY
			self.thick_grid.stroke_color = GRAY
	
	def set_gui(self):
		w, h = self.size
		l = min(w / 16, 64)
		lh = l / 2
		m = min(h / 16, 48)
		mh = m / 2
		
		# 機能
		self.gui_undo = Gui(self, l, 'files/gui/undo.png')
		self.gui_undo.position = (l * 0.5, lh)
		self.gui_undo.action = self.bt_undo
		
		self.gui_redo = Gui(self, l, 'files/gui/redo.png')
		self.gui_redo.position = (l * 1.5, lh)
		self.gui_redo.action = self.bt_redo
		
		self.gui_open = Gui(self, l, 'files/gui/open.png')
		self.gui_open.position = (l * 2.5, lh)
		self.gui_open.action = self.bt_open
		
		self.gui_download = Gui(self, l, 'files/gui/download.png')
		self.gui_download.position = (l * 3.5, lh)
		self.gui_download.action = self.bt_download
		
		self.gui_resize = Gui(self, l, 'files/gui/resize.png')
		self.gui_resize.position = (l * 4.5, lh)
		self.gui_resize.action = self.bt_resize
		
		self.gui_clear = Gui(self, l, 'files/gui/clear.png')
		self.gui_clear.position = (l * 5.5, lh)
		self.gui_clear.action = self.bt_clear
		
		self.gui_zoom_in = Gui(self, l, 'files/gui/zoom_in.png')
		self.gui_zoom_in.position = (l * 6.5, lh)
		self.gui_zoom_in.action = self.bt_zoom_in
		
		self.gui_zoom_out = Gui(self, l, 'files/gui/zoom_out.png')
		self.gui_zoom_out.position = (l * 7.5, lh)
		self.gui_zoom_out.action = self.bt_zoom_out
		
		self.gui_option = Gui(self, l, 'files/gui/option.png')
		self.gui_option.position = (l * 8.5, lh)
		self.gui_option.action = self.bt_option
		
		self.gui_center = Gui(self, l, 'files/gui/center.png')
		self.gui_center.position = (l * 9.5, lh)
		self.gui_center.action = self.bt_center
		
		self.gui_bg_invert = Gui(self, l, 'files/gui/bg_invert.png')
		self.gui_bg_invert.position = (l * 10.5, lh)
		self.gui_bg_invert.action = self.bt_bg_invert
		
		self.gui_layer_edit = Gui(self, l, 'files/gui/layer_edit.png')
		self.gui_layer_edit.position = (l * 11.5, lh)
		self.gui_layer_edit.action = self.bt_layer_edit
		
		self.gui_palette_edit = Gui(self, l, 'files/gui/palette_edit.png')
		self.gui_palette_edit.position = (l * 12.5, lh)
		self.gui_palette_edit.action = self.bt_palette_edit
		
		self.gui_anim = Gui(self, l, 'files/gui/anim.png')
		self.gui_anim.position = (l * 13.5, lh)
		self.gui_anim.action = self.bt_anim
		
		self.gui_switch = Gui(self, l, 'files/gui/switch.png')
		self.gui_switch.position = (l * 14.5, lh)
		self.gui_switch.action = self.bt_switch
		
		self.lay_selector = ui.ScrollView()
		self.lay_selector.frame = (l * 3, h, l * 10, l * 1.5)
		self.lay_selector.border_color = '#adadad'
		self.lay_selector.border_width = 2
		self.view.add_subview(self.lay_selector)
		
		# 道具
		self.gui_pencil = Gui(self, m, 'files/gui/tool_pencil.png')
		self.gui_pencil.position = (mh, h - m * 3)
		self.gui_pencil.action = self.select_pencil
		
		self.gui_eraser = Gui(self, m, 'files/gui/tool_eraser.png')
		self.gui_eraser.position = (mh, h - m * 4)
		self.gui_eraser.action = self.select_eraser
		
		self.gui_picker = Gui(self, m, 'files/gui/tool_picker.png')
		self.gui_picker.position = (mh, h - m * 5)
		self.gui_picker.action = self.select_picker
		
		self.gui_cap = Gui(self, m, 'files/gui/tool_cap.png')
		self.gui_cap.position = (mh, h - m * 6)
		self.gui_cap.action = self.select_cap
		
		self.gui_fill = Gui(self, m, 'files/gui/tool_fill.png')
		self.gui_fill.position = (mh, h - m * 7)
		self.gui_fill.action = self.select_fill
		
		self.gui_rect = Gui(self, m, 'files/gui/tool_rect.png')
		self.gui_rect.position = (mh, h - m * 8)
		self.gui_rect.action = self.select_rect
		
		self.gui_circle = Gui(self, m, 'files/gui/tool_circle.png')
		self.gui_circle.position = (mh, h - m * 9)
		self.gui_circle.action = self.select_circle
		
		self.gui_line = Gui(self, m, 'files/gui/tool_line.png')
		self.gui_line.position = (mh, h - m * 10)
		self.gui_line.action = self.select_line
		
		self.gui_move = Gui(self, m, 'files/gui/tool_move.png')
		self.gui_move.position = (mh, h - m * 12)
		self.gui_move.action = self.select_move
		
		self.gui_color_change = Gui(self, m, 'files/gui/color_change.png')
		self.gui_color_change.position = (w - mh, h - m * 3)
		self.gui_color_change.action = self.bt_color_change
		
		self.gui_color_frame = ShapeNode(
			ui.Path.rect(2, 2, m - 4, m - 4), CLEAR, WHITE)
		self.gui_color_frame.position = (w - mh, h - m * 5)
		self.gui_color_frame.line_width = 4
		self.gui_color_frame.z_position = 256
		self.add_child(self.gui_color_frame)
		
		self.gui_color0 = GuiColor(self, m, '#000000', 0)
		self.gui_color0.position = (w - mh, h - m * 5)
		self.gui_color0.action = self.bt_color
		
		self.gui_color1 = GuiColor(self, m, '#ff0000', 1)
		self.gui_color1.position = (w - mh, h - m * 6)
		self.gui_color1.action = self.bt_color
		
		self.gui_color2 = GuiColor(self, m, '#00ff00', 2)
		self.gui_color2.position = (w - mh, h - m * 7)
		self.gui_color2.action = self.bt_color
		
		self.gui_color3 = GuiColor(self, m, '#0000ff', 3)
		self.gui_color3.position = (w - mh, h - m * 8)
		self.gui_color3.action = self.bt_color
		
		self.gui_color4 = GuiColor(self, m, '#00ffff', 4)
		self.gui_color4.position = (w - mh, h - m * 9)
		self.gui_color4.action = self.bt_color
		
		self.gui_color5 = GuiColor(self, m, '#ff00ff', 5)
		self.gui_color5.position = (w - mh, h - m * 10)
		self.gui_color5.action = self.bt_color
		
		self.gui_color6 = GuiColor(self, m, '#ffff00', 6)
		self.gui_color6.position = (w - mh, h - m * 11)
		self.gui_color6.action = self.bt_color
		
		self.gui_color7 = GuiColor(self, m, '#8080ff', 7)
		self.gui_color7.position = (w - mh, h - m * 12)
		self.gui_color7.action = self.bt_color

if __name__ == '__main__':
	run(MyScene(), show_fps=True)
