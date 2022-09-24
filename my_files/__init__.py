import os


my_files = os.path.dirname(__file__)


def get_path(folder, name):
	return os.path.join(my_files, folder, name)


def get_font(name):
	return get_path('fonts', name)
