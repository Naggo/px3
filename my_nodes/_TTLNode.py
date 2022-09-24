from PIL import Image, ImageDraw, ImageFont
import numpy
import scene
import sound
from my_funcs import cmd_split, pil2tex
A = scene.Action


class TTLNode(scene.SpriteNode):
	"""
	Argument:
		text = str(text)
		font = tuple(path, size)
		line_height = int(height) | None
		filtering_mode = scene.filtering_mode
		bg_color = str(name) | str(#hex) | tuple(0~255 *3~4)
		sound_effect = *args -> sound.play_effect(name[, volume, pitch, pan, looping])
	Escape:
		\< (Outside the command)
		\> (Inside the command)
	Names(namespace in command):
		font = current font size
		node = self
	Command:
		<c:[color]>
		<f:[index*]>
		<st:([color]):([font index*]):[text]>
		<lh:[height*]>
		<[other]:[comment]>
		
		<w:[time*]>
		<mv:([x*]):([y*])>
		<exe:[code*]>
		<exe::[code*]> -> command only
		<str:[expression*]>
		<i:[interval*]>
		<se:[args*]>
		<sk:[text]:[count*]>
			*: Can use namespace.
	--------------------------------
	"""
	global_names = {}
	
	def __init__(
			self, text, font=('Helvetica', 20), line_height=None,
			filtering_mode=scene.FILTERING_LINEAR, bg_color=(0, 0, 0, 0),
			sound_effect=None, *args, **kwargs):
		
		scene.SpriteNode.__init__(self, None, *args, **kwargs)
		self.size = (0, 0)
		
		self.text = text
		# ->self._text_list
		self.font = font
		# ->self._fonts_list
		
		self._text_index = 0
		self._list_index = 0
		
		self.next_point = numpy.array([0, 0])
		self.origin_point = numpy.array([0, 0])
		
		self._img = None
		self._draw = None
		self.bg_color = bg_color
		self.auto_anchor = True
		self.origin_anchor = (0, 0)
		
		self.names = {
			'font': self._fonts_list[0].size,
			'node': self
		}
		self.__auto_running = False
		self.filtering_mode = filtering_mode
		
		self.text_color = '#ffffff'
		self.font_index = 0
		self.move_point = numpy.array([0, 0])
		self.interval = 0.005
		self.sound_effect = sound_effect
		
		if line_height is None:
			self.line_height = self.names['font']
		else:
			self.line_height = line_height
		
		self._draw_action = self._draw_char
		
	@property
	def text(self):
		return self.__text
		
	@text.setter
	def text(self, text):
		self.__text = text
		if text.startswith('\n'):
			text = text[1:]
		if text.endswith('\n'):
			text = text[:-1]
		self._text_list = cmd_split(text, True)
	
	@property
	def font(self):
		return self.__font
	
	@font.setter
	def font(self, font):
		try:
			if isinstance(font, list):
				self._fonts_list = [ImageFont.truetype(*path) for path in font]
			else:
				self._fonts_list = [ImageFont.truetype(*font)]
		except AttributeError:
			pass
		else:
			self.__font = font
	
	@property
	def font_index(self):
		return self.__font_index
	
	@font_index.setter
	def font_index(self, index):
		if index < len(self._fonts_list):
			self.__font_index = index
	
	@property
	def interval(self):
		return self.__interval
		
	@interval.setter
	def interval(self, interval):
		try:
			self.__interval = float(interval)
		except ValueError:
			pass
		else:
			if self.auto_running:
				if interval:
					call = A.sequence(A.call(self._auto_update), A.wait(interval))
				else:
					call = A.call(self._auto_update)
				self.repeat_action = A.repeat_forever(call)
				self.run_action(self.repeat_action, 'auto')
	
	@property
	def sound_effect(self):
		return self.__sound_effect
	
	@sound_effect.setter
	def sound_effect(self, sound_effect):
		if isinstance(sound_effect, str):
			sound_effect = (sound_effect,)
		self.__sound_effect = sound_effect
	
	@property
	def image(self):
		return self._img
	
	@property
	def auto_running(self):
		return self.__auto_running
	
	def eval(self, exp):
		return eval(exp, self.global_names, self.names)
	
	def pil2tex(self):
		self.texture = pil2tex(self.image)
		self.texture.filtering_mode = self.filtering_mode
	
	def auto_start(self):
		if self.image is None:
			self.new_image()
		if self.interval:
			call = A.sequence(A.call(self._auto_update), A.wait(self.interval))
		else:
			call = A.call(self._auto_update)
		self._repeat_action = A.repeat_forever(call)
		self.run_action(self._repeat_action, 'auto')
		self.__auto_running = True
	
	def _auto_update(self):
		if self.next_char():
			self.auto_stop()
	
	def auto_stop(self):
		self.remove_action('auto')
		self.__auto_running = False
		self.when_stopped()
	
	def when_stopped(self):
		pass
	
	def auto_wait(self, t):
		if self.auto_running:
			self.remove_action('auto')
			self.run_action(A.sequence(A.wait(t), A.call(self._auto_restart)), 'wait')
	
	def _auto_restart(self):
		self.run_action(self._repeat_action, 'auto')
	
	def text_skip(self):
		if self.image is None:
			self.new_image()
		call = A.call(self._auto_update)
		self.repeat_action = A.repeat_forever(call)
		self.__auto_running = False
		self._draw_action = self._draw_text
		self.run_action(self.repeat_action, 'auto')
	
	def clear(self):
		self.remove_all_actions()
		self.__auto_running = False
		self._img = None
		self.size = (0, 0)
		self._draw_action = self._draw_char
		
		self._text_index = 0
		self._list_index = 0
		self.next_point[:] = 0  # all
		
		self.text_color = '#ffffff'
		self.font_index = 0
		self.move_point[:] = 0
		self.interval = 0.005
	
	def getsize(self):
		min_x = 0
		min_y = 0
		max_x = 0
		max_y = 0
		next_x = 0
		next_y = 0
		move_x = 0
		move_y = 0
		font_index = 0
		line_height = self.line_height
		
		def draw_sim(text, f_index):
			nonlocal min_x, min_y, max_x, max_y, next_x, next_y
			split = text.split('\n')
			font = self._fonts_list[f_index]
			w, h = font.getsize(split[0])
			min_x = min(min_x, next_x + move_x)
			min_y = min(min_y, next_y + move_y)
			next_x += w
			max_x = max(max_x, next_x + move_x)
			max_y = max(max_y, next_y + move_y + h)
			for line in split[1:]:
				w, h = font.getsize(line)
				next_y += line_height
				min_x = min(min_x, move_x)
				min_y = min(min_y, move_y)
				next_x = w
				max_x = max(max_x, next_x + move_x)
				max_y = max(max_y, next_y + move_y + h)
		
		for index, text in enumerate(self._text_list):
			if index % 2:
				# cmd
				if text is None:
					break
				key, value = text.split(':', 1)
				
				if key == 'f':
					# フォントの変更
					font_index = self.eval(value)
					
				elif key == 'st':
					# 特殊な文
					color, f_index, text = [v.strip() for v in value.split(':', 2)]
					if f_index:
						f_index = self.eval(f_index)
					else:
						f_index = font_index
					draw_sim(text, f_index)
						
				elif key == 'lh':
					# 行送りの高さの変更
					line_height = self.eval(value)
				
				elif key == 'mv':
					# 移動
					x, y = [self.eval(v) if v else 0 for v in value.split(':', 1)]
					move_x += x
					move_y += y
				
				elif key == 'str':
					# 式
					text = str(self.eval(value))
					draw_sim(text, font_index)
				
				elif key == 'sk':
					# 飛ばす
					text, count = value.split(':', 1)
					font = self._fonts_list[font_index]
					if not text:
						text = ' '
					w = font.getsize(text)[0] * self.eval(count)
					next_x += w
				
			else:
				# txt
				draw_sim(text, font_index)
		
		return min_x, min_y, max_x, max_y
	
	def new_image(self):
		min_x, min_y, max_x, max_y = self.getsize()
		abs_min_x = abs(min_x)
		abs_min_y = abs(min_y)
		self.origin_point = numpy.array([abs_min_x, abs_min_y])
		w = abs_min_x + max_x
		h = abs_min_y + max_y
		size = (int(w), int(h))
		x = min_x / w
		y = max_y / h
		self.origin_anchor = (x, y)
		if self.auto_anchor:
			self.anchor_point = self.origin_anchor
		self._img = Image.new('RGBA', size, self.bg_color)
		self._draw = ImageDraw.Draw(self._img)
		self.pil2tex()
		
	def next_char(self):
		try:
			text = self._text_list[self._list_index]
		except IndexError:
			return True
		
		if self._list_index % 2:
			# command
			if text is None:
				return True
			key, value = text.split(':', 1)
			
			if key == 'c':
				# 色の変更
				if value.startswith('('):
					self.text_color = self.eval(value)
				else:
					self.text_color = value
				self._list_index += 1
				return self.next_char()
			
			elif key == 'f':
				# フォントの変更
				self.font_index = self.eval(value)
				self.names['font'] = self._fonts_list[self.font_index].size
				self._list_index += 1
				return self.next_char()
			
			elif key == 'st':
				# 特殊な文
				color, f_index, text = [v.strip() for v in value.split(':', 2)]
				# 色
				if color:
					if color.startswith('('):
						color = self.eval(color)
				else:
					color = self.text_color
				# フォント
				if f_index:
					f_index = self.eval(f_index)
				else:
					f_index = self.font_index
				# 文
				return self._draw_action(text, color, f_index)
			
			elif key == 'lh':
				# 行送りの高さの変更
				self.line_height = self.eval(value)
				self._list_index += 1
				return self.next_char()
				
			elif key == 'w':
				# 待機
				self.auto_wait(self.eval(value))
				self._list_index += 1
				return False
			
			elif key == 'mv':
				# 移動
				self.move_point += [self.eval(v) if v else 0 for v in value.split(':', 1)]
				self._list_index += 1
				return self.next_char()
			
			elif key == 'exe':
				# 文の実行
				only = value.startswith(':')
				if only:
					value = value[1:]
				exec(value, self.global_names, self.names)
				self._list_index += 1
				if only:
					return False
				else:
					return self.next_char()
			
			elif key == 'str':
				# 式
				text = str(self.eval(value))
				return self._draw_action(text, self.text_color, self.font_index)
			
			elif key == 'i':
				# 間隔の変更
				self.interval = self.eval(value)
				self._list_index += 1
				if self.auto_running:
					return False
				else:
					return self.next_char()
			
			elif key == 'se':
				# 効果音の変更
				se = self.eval(value)
				self.sound_effect = se
				self._list_index += 1
				return self.next_char()
				
			elif key == 'sk':
				# 飛ばす
				text, count = value.split(':', 1)
				font = self._fonts_list[self.font_index]
				if not text:
					text = ' '
				w = font.getsize(text)[0] * self.eval(count)
				self.next_point[0] += w
				self._list_index += 1
				return self.next_char()
			
			else:
				self._list_index += 1
				return self.next_char()
				
		else:
			# text
			return self._draw_action(text, self.text_color, self.font_index)
	
	def _draw_char(self, text, color, f_index):
		try:
			char = text[self._text_index]
		except IndexError:
			self._text_index = 0
			self._list_index += 1
			return self.next_char()
		self._text_index += 1
		
		if char == '\n':
			self.next_point[0] = 0
			self.next_point[1] += self.line_height
			return self.next_char()
		
		font = self._fonts_list[f_index]
		w = font.getsize(char)[0]
		
		if char.isspace():
			self.next_point[0] += w
			return False
		
		if self.sound_effect is not None:
			sound.play_effect(*self.sound_effect)
		
		point = self.next_point + self.origin_point + self.move_point
		self._draw.text(point, char, color, font=font, anchor='lt')
		self.next_point[0] += w
		
		self.pil2tex()
		return False
	
	def _draw_text(self, text, color, f_index):
		try:
			text = text[self._text_index:]
		except IndexError:
			self._text_index = 0
			self._list_index += 1
			return self.next_char()
		self._text_index = 0
		
		if self.sound_effect is not None:
			sound.play_effect(*self.sound_effect)
		
		split = text.split('\n')
		font = self._fonts_list[f_index]
		point = self.next_point + self.origin_point + self.move_point
		self._draw.text(point, split[0], color, font=font, anchor='lt')
		self.next_point[0] += font.getsize(split[0])[0]
		for line in split[1:]:
			self.next_point[0] = 0
			self.next_point[1] += self.line_height
			point = self.next_point + self.origin_point + self.move_point
			self._draw.text(point, line, color, font=font, anchor='lt')
			self.next_point[0] = font.getsize(line)[0]
		
		self._list_index += 1
		self.pil2tex()
		return False
