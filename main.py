from kivy.app import App
from kivy.uix.label import Label


class SakuraApp(App):
    def build(self):
        return Label(text="Sakura Project")


if __name__ == "__main__":
    SakuraApp().run()
