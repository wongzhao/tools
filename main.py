from textual.app import App
from textual.widgets import Footer


class Main(App):
	SCREENS = {}
	BINDINGS = []

	def compose(self):
		yield Footer()


if __name__ == "__main__":
	app = Main()
	app.run()
