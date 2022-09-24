import ui


class MoveView(ui.View):
	def __init__(self):
		self._start_point = ui.Point()
		self._held = False
	
	def touch_began(self, touch):
		self._start_point = touch.location
		if not self._held:
			self._bg_col = self.background_color
		self.background_color = tuple(v - 0.1 for v in self.background_color[0:3])
		self._held = True
	
	def touch_moved(self, touch):
		x, y = touch.location - self._start_point
		self.x = max(0, min(self.x + x, self.superview.width - self.width))
		self.y = max(0, min(self.y + y, self.superview.height - self.height))
	
	def touch_ended(self, touch):
		self.background_color = self._bg_col
		self._held = False


class HandleView(MoveView):
	def touch_moved(self, touch):
		x, y = touch.location - self._start_point
		sv = self.superview
		sv.x = max(0, min(sv.x + x, sv.superview.width - sv.width))
		sv.y = max(0, min(sv.y + y, sv.superview.height - sv.height))
