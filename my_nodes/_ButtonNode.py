import scene
import sound
import weakref


class ButtonNode(scene.SpriteNode):
	TYPE_DEFAULT = 0
	TYPE_TOUCH = 1
	TYPE_RELEASE = 2
	buttons = []
	
	def __init__(self, *args, **kwargs):
		scene.SpriteNode.__init__(self, *args, **kwargs)
		self.__pushed = False
		self.type = self.TYPE_DEFAULT
		self.action = lambda bt: None
		
		self.normal_color = 'white'
		self.pushed_color = (0.6, 0.6, 0.6, 1.0)
		self.sound_effect = None
		
		ref = weakref.ref(self)
		self.buttons.append(ref)
		weakref.finalize(self, self.buttons.remove, ref)
	
	@property
	def normal_color(self):
		return self.__normal_color
	
	@normal_color.setter
	def normal_color(self, col):
		self.__normal_color = col
		if not self.is_pushed:
			self.color = col
	
	@property
	def pushed_color(self):
		return self.__pushed_color
	
	@pushed_color.setter
	def pushed_color(self, col):
		self.__pushed_color = col
		if self.is_pushed:
			self.color = col
	
	@property
	def sound_effect(self):
		return self.__sound_effect
	
	@sound_effect.setter
	def sound_effect(self, sound_effect):
		if isinstance(sound_effect, str):
			sound_effect = (sound_effect,)
		self.__sound_effect = sound_effect
	
	@property
	def is_pushed(self):
		return self.__pushed
	
	@classmethod
	def detect_began(cls, touch):
		flag = False
		for ref in cls.buttons:
			bt = ref()
			if touch.location in bt.frame:
				if bt.type is cls.TYPE_TOUCH and not flag:
					if bt.sound_effect is not None:
						sound.play_effect(*bt.sound_effect)
					bt.action(bt)
				bt.__pushed = True
				bt.color = bt.pushed_color
				flag = True
		return flag
	
	@classmethod
	def detect_moved(cls, touch):
		flag = False
		for ref in cls.buttons:
			bt = ref()
			if touch.location in bt.frame:
				bt.color = bt.pushed_color
				flag = True
			else:
				bt.color = bt.normal_color
		return flag
	
	@classmethod
	def detect_ended(cls, touch):
		flag = False
		for ref in cls.buttons:
			bt = ref()
			if touch.location in bt.frame and not flag:
				is_default = bt.type is cls.TYPE_DEFAULT
				is_release = bt.type is cls.TYPE_RELEASE
				if is_release or (is_default and bt.is_pushed):
					if bt.sound_effect is not None:
						sound.play_effect(*bt.sound_effect)
					bt.action(bt)
					flag = True
			bt.__pushed = False
			bt.color = bt.normal_color
		return flag
	
	@classmethod
	def sort_by_z(cls):
		cls.buttons.sort(key=lambda ref: ref().z_position, reverse=True)
