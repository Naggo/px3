from PIL import Image, ImageDraw, ImageFont


def cmd_split(string, single=False):
	text_list = []
	cmd_list = []
	
	if single:
		cmd_list = text_list
	
	start = 0
	while True:
		index = string.find('<', start)
		escaped = (0 < index) and string[index - 1] == '\\'
		found = index != -1
		closed = '>' in string
		
		if escaped:
			string = string.replace('\<', '<', 1)
			start = index
			continue
		elif found and closed:
			text = string[:index]
			
			close_index = string.find('>', index)
			close_escaped = string[close_index - 1] == '\\'
			while close_escaped:
				string = string.replace('\>', '>', 1)
				close_index = string.find('>', close_index)
				close_escaped = string[close_index - 1] == '\\'
			
			cmd = string[index + 1:close_index]
			string = string[close_index + 1:]
			start = 0
		else:
			text = string
			cmd = 1
		
		text_list.append(text)
		if (cmd == 1) or (not found):
			cmd_list.append(None)
			break
		cmd_list.append(cmd)
	
	if single:
		return text_list
	return text_list, cmd_list


def text2image(string, font, line_height=None, bg_color=(0, 0, 0, 0)):
	"""
	Argument:
		string = str(text)
		font = tuple(path, size)
		line_height = int(height) | None
		bg_color = str(name) | str(#hex) | tuple(0~255 *3~4)
	Escape:
		\< (Outside the command)
		\> (Inside the command)
	Command:
		<c:[color]>
		<f:[index]>
		<st:([color]):([font index]):[text]>
		<lh:[formula]>  # 'font' will be replaced with the current font size
		<[other]:[comment]>
	"""
	
	# フォントの読み込み
	if type(font) is list:
		fonts_list = [ImageFont.truetype(*path) for path in font]
		font = fonts_list[0]
	else:
		font = ImageFont.truetype(*font)
		fonts_list = [font]
	if line_height is None:
		line_height = font.__dict__['size']
	
	# 最初と最後の改行を削除
	if string.startswith('\n'):
		string = string[1:]
	if string.endswith('\n'):
		string = string[:-1]
	
	# 文とコマンドを分ける
	text_list, cmd_list = cmd_split(string)
	
	# サイズの計測
	w = 0
	h = line_height
	width = 0
	height = line_height
	sizefont = font
	for text, command in zip(text_list, cmd_list):
		if text:
			split = text.split('\n')
			w += sizefont.getsize(split[0])[0]
			width = max(width, w)
			for line in split[1:]:
				height += h
				w = sizefont.getsize(line)[0]
				width = max(width, w)
		if command:
			key, value = [c.strip() for c in command.split(':', 1)]
			
			if key == 'f':  # f -フォントの変更
				sizefont = fonts_list[int(value)]
			
			elif key == 'st':  # st -特殊な文
				st_col, st_findex, st_tx = [v.strip() for v in value.split(':', 2)]
				
				if st_findex:
					st_font = fonts_list[int(st_findex)]
				else:
					st_font = sizefont
				
				split = st_tx.split('\n')
				w += st_font.getsize(split[0])[0]
				width = max(width, w)
				for line in split[1:]:
					height += h
					w = st_font.getsize(line)[0]
					width = max(width, w)
			
			elif key == 'lh':  # lh -行送りの高さの変更
				value = value.replace('font', str(sizefont.__dict__['size']))
				h = int(eval(value))
					
	# 画像の作成
	size = (width, height)
	img = Image.new("RGBA", size, bg_color)
	draw = ImageDraw.Draw(img)
	
	# draw
	x = 0
	y = 0
	color = '#000000'
	for text, command in zip(text_list, cmd_list):
		if text:
			split = text.split('\n')
			draw.text((x, y), split[0], color, font=font, anchor='ls')
			x += font.getsize(split[0])[0]
			for line in split[1:]:
				y += line_height
				draw.text((0, y), line, color, font=font, anchor='ls')
				x = font.getsize(line)[0]
		if command:
			key, value = [c.strip() for c in command.split(':', 1)]
			
			if key == 'c':  # c -色の変更
				if value.startswith('('):
					color = eval(value)
				else:
					color = value
			
			elif key == 'f':  # f -フォントの変更
				font = fonts_list[int(value)]
			
			elif key == 'st':  # st -特殊な文
				st_col, st_findex, st_tx = [v.strip() for v in value.split(':', 2)]
				
				if st_col:
					if st_col.startswith('('):
						st_col = eval(st_col)
				else:
					st_col = color
				
				if st_findex:
					st_font = fonts_list[int(st_findex)]
				else:
					st_font = font
				
				split = st_tx.split('\n')
				draw.text((x, y), split[0], st_col, font=st_font, anchor='ls')
				x += st_font.getsize(split[0])[0]
				for line in split[1:]:
					y += line_height
					draw.text((0, y), line, st_col, font=st_font, anchor='ls')
					x = st_font.getsize(line)[0]
			
			elif key == 'lh':  # lh -行送りの高さの変更
				value = value.replace('font', str(font.__dict__['size']))
				line_height = int(eval(value))
	
	return img
