from PIL import Image, ImageDraw, ImageFont
import scene
import sound
from my_funcs import cmd_split, pil2tex
A = scene.Action


class CharNode(scene.SpriteNode):
	def __init__(self, char, text_color, font, *args, **kwargs):
		size = font.getsize(char)
		img = Image.new("RGBA", size)
		draw = ImageDraw.Draw(img)
		draw.text((1, 0), char, text_color, font, anchor='lt')
		tex = pil2tex(img)
		
		scene.SpriteNode.__init__(self, tex, *args, **kwargs)
		self.anchor_point = (0, 1)
		self.char = char
		self.text_color = text_color
		self.font = font
	
	def update(self):
		size = self.font.getsize(self.char)
		img = Image.new("RGBA", size)
		draw = ImageDraw.Draw(img)
		draw.text((0, 0), self.char, self.text_color, self.font, anchor='lt')
		self.texture = pil2tex(img)


class MsgNode(scene.Node):
	"""
	Argument:
		text = str(text)
		font = tuple(path, size)
		line_height = int(height) | None
		filtering_mode = scene.filtering_mode
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
			filtering_mode=scene.FILTERING_LINEAR, sound_effect=None, *args, **kwargs):
		
		scene.Node.__init__(self, *args, **kwargs)
		
		self.text = text
		# ->self._text_list
		self.font = font
		# ->self._fonts_list
		
		self._text_index = 0
		self._list_index = 0
		
		self.next_point = scene.Point()
		
		self.names = {
			'font': self._fonts_list[0].size,
			'node': self
		}
		self.chars = []
		self.__auto_running = False
		self.filtering_mode = filtering_mode
		
		self.text_color = '#ffffff'
		self.font_index = 0
		self.move_point = scene.Point()
		self.interval = 0.005
		self.sound_effect = sound_effect
		
		if line_height is None:
			self.line_height = self.names['font']
		else:
			self.line_height = line_height
		
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
	def auto_running(self):
		return self.__auto_running
	
	def eval(self, exp):
		return eval(exp, self.global_names, self.names)
	
	def auto_start(self):
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
	
	def clear(self):
		self.remove_all_actions()
		for node in list(self.chars):
			node.remove_from_parent()
			self.chars.remove(node)
		
		self._text_index = 0
		self._list_index = 0
		self.next_point = scene.Point()
		
		self.text_color = '#ffffff'
		self.font_index = 0
		self.move_point = scene.Point()
		self.interval = 0.005
	
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
				return self._make_char(text, color, f_index)
			
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
				x, y = [self.eval(v) if v else 0 for v in value.split(':', 1)]
				self.move_point += scene.Point(x, -y)
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
				return self._make_char(text, self.text_color, self.font_index)
			
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
				self.next_point.x += w
				self._list_index += 1
				return self.next_char()
			
			else:
				self._list_index += 1
				return self.next_char()
				
		else:
			# text
			return self._make_char(text, self.text_color, self.font_index)
			
	def _make_char(self, text, color, f_index):
		try:
			char = text[self._text_index]
		except IndexError:
			self._text_index = 0
			self._list_index += 1
			return self.next_char()
		self._text_index += 1
		
		if char == '\n':
			self.next_point.x = 0
			self.next_point.y -= self.line_height
			return self.next_char()
		
		font = self._fonts_list[f_index]
		
		if char.isspace():
			self.next_point.x += font.getsize(char)[0]
			return False
		
		if self.sound_effect is not None:
			sound.play_effect(*self.sound_effect)
		
		node = CharNode(char, color, font)
		node.position = self.next_point + self.move_point
		node.texture.filtering_mode = self.filtering_mode
		self.add_child(node)
		self.chars.append(node)
		self.next_point.x += node.size.w
		return False
