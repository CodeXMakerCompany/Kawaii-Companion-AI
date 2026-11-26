"""The GL side of drawing: UI layers as textures blended over the model, and pixel readbacks."""

import numpy as np
from OpenGL import GL


class OverlayTexture:
    """A UI layer as one GL texture, blended over the model with a single quad (the whole
    window by default, or a small rectangle such as the system monitor)."""

    def __init__(self, w, h):
        self.tex = GL.glGenTextures(1)
        GL.glBindTexture(GL.GL_TEXTURE_2D, self.tex)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MIN_FILTER, GL.GL_NEAREST)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MAG_FILTER, GL.GL_NEAREST)
        self.resize(w, h)

    def resize(self, w, h):
        self.w, self.h = w, h
        GL.glBindTexture(GL.GL_TEXTURE_2D, self.tex)
        GL.glTexImage2D(GL.GL_TEXTURE_2D, 0, GL.GL_RGBA8, w, h, 0, GL.GL_RGBA, GL.GL_UNSIGNED_BYTE, None)

    def upload(self, data, fmt=GL.GL_RGBA):
        """fmt: GL_BGRA for cairo surfaces (premultiplied too)."""
        GL.glBindTexture(GL.GL_TEXTURE_2D, self.tex)
        GL.glTexSubImage2D(GL.GL_TEXTURE_2D, 0, 0, 0, self.w, self.h, fmt, GL.GL_UNSIGNED_BYTE, data)

    def draw(self, x=0, y=0, window_h=None):
        """x, y: top-left in window coords (window_h needed to flip to GL's bottom-left)."""
        # Cubism leaves its shader/buffers bound; reset to plain fixed-function state.
        GL.glUseProgram(0)
        GL.glBindBuffer(GL.GL_ARRAY_BUFFER, 0)
        GL.glViewport(int(x), int((window_h - y - self.h) if window_h else 0), self.w, self.h)
        for cap in (GL.GL_CULL_FACE, GL.GL_DEPTH_TEST, GL.GL_STENCIL_TEST, GL.GL_SCISSOR_TEST):
            GL.glDisable(cap)
        GL.glEnable(GL.GL_BLEND)
        GL.glBlendFunc(GL.GL_ONE, GL.GL_ONE_MINUS_SRC_ALPHA)  # texture is premultiplied
        GL.glActiveTexture(GL.GL_TEXTURE0)
        GL.glEnable(GL.GL_TEXTURE_2D)
        GL.glBindTexture(GL.GL_TEXTURE_2D, self.tex)
        GL.glColor4f(1, 1, 1, 1)
        GL.glBegin(GL.GL_QUADS)  # rows are top-down, so v=0 is the top edge
        GL.glTexCoord2f(0, 1); GL.glVertex2f(-1, -1)
        GL.glTexCoord2f(1, 1); GL.glVertex2f(1, -1)
        GL.glTexCoord2f(1, 0); GL.glVertex2f(1, 1)
        GL.glTexCoord2f(0, 0); GL.glVertex2f(-1, 1)
        GL.glEnd()
        GL.glDisable(GL.GL_TEXTURE_2D)


def read_alpha(left, model_w, model_h):
    """Her coverage mask (rows top-down) from the frame just drawn; model pixels only."""
    data = GL.glReadPixels(left, 0, model_w, model_h, GL.GL_RGBA, GL.GL_UNSIGNED_BYTE)
    return np.frombuffer(data, np.uint8).reshape(model_h, model_w, 4)[::-1, :, 3] > 8


def write_snapshot(path, w, h):
    from PIL import Image

    GL.glReadBuffer(GL.GL_BACK)
    data = GL.glReadPixels(0, 0, w, h, GL.GL_RGBA, GL.GL_UNSIGNED_BYTE)
    img = np.frombuffer(data, np.uint8).reshape(h, w, 4)[::-1].astype(np.float32)
    alpha = img[..., 3:4]
    img[..., :3] = np.where(alpha > 0, img[..., :3] * 255.0 / np.maximum(alpha, 1), 0)  # un-premultiply
    Image.fromarray(img.clip(0, 255).astype(np.uint8), "RGBA").save(path)
    print(f"snapshot {path} {w}x{h}")
