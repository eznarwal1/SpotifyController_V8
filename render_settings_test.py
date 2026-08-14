import os
import sys

# make companion/ discoverable so its local imports (e.g. 'themes') work
sys.path.insert(0, os.path.join(os.getcwd(), "companion"))
from v8_renderer import render_view
from v8_controller import V8Controller

v8 = V8Controller()
v8.state.view = 'settings'

# build a minimal theme dict expected by renderer
theme = {
    'background': [20,20,20],
    'panel': [40,40,40],
    'primary': [255,255,255],
    'secondary': [180,180,180],
    'accent': [100,200,255],
    'ui_brightness': v8.state.brightness
}

img = render_view(
    view='settings',
    theme=theme,
    queue=[],
    queue_index=0,
    queue_source='',
    queue_available=False,
    queue_status='',
    mixer=[],
    mixer_index=0,
    themes=[],
    theme_index=0,
)
print('render len', len(img))
