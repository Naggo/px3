from draw import MyScene
import scene


with open('latest.txt') as f:
	path = f.read()

MyScene.folder_name = path
mysc = MyScene()
scene.run(mysc, show_fps=True)

mysc.new_message(f'RECALL: [<st:yellow::{path}>]')


