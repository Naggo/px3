def get_module(name):
	exec('from . import ' + name)
	return eval(name)
