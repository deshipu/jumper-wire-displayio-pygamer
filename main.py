import analogio
import displayio
import digitalio
import board
import gamepadshift
import time
import supervisor

import adafruit_imageload.bmp as bmp


last_tick = time.monotonic()


def collide(ax0, ay0, ax1, ay1, bx0, by0, bx1=None, by1=None):
    if bx1 is None:
        bx1 = bx0
    if by1 is None:
        by1 = by0
    return not (ax1 < bx0 or ay1 < by0 or ax0 > bx1 or ay0 > by1)


def tick(fps):
    global last_tick
    last_tick += 1 / fps
    wait = max(0, last_tick - time.monotonic())
    if wait:
        time.sleep(wait)
    else:
        last_tick = time.monotonic()


class PyGamerButtons:
    K_X = 0x01
    K_O = 0x02
    K_START = 0x04
    K_SELECT = 0x08
    K_DOWN = 0x10
    K_LEFT = 0x20
    K_RIGHT = 0x40
    K_UP = 0x80

    def __init__(self):
        self.buttons = gamepadshift.GamePadShift(
            digitalio.DigitalInOut(board.BUTTON_CLOCK),
            digitalio.DigitalInOut(board.BUTTON_OUT),
            digitalio.DigitalInOut(board.BUTTON_LATCH),
        )
        self.joy_x = analogio.AnalogIn(board.JOYSTICK_Y)
        self.joy_y = analogio.AnalogIn(board.JOYSTICK_X)

    def get_pressed(self):
        pressed = self.buttons.get_pressed()
        dead = 15000
        x = self.joy_x.value - 32767
        if x < -dead:
            pressed |= self.K_LEFT
        elif x > dead:
            pressed |= self.K_RIGHT
        y = self.joy_y.value - 32767
        if y < -dead:
            pressed |= self.K_UP
        elif y > dead:
            pressed |= self.K_DOWN
        return pressed


class Level:
    def __init__(self, root):
        self.load_graphics()
        self.make_grids()
        self.load_map("level.bmp")
        self.fill_grids()
        root.append(self.back)
        root.append(self.walls)

    def load_graphics(self):
        with open("jumper-walls.bmp", 'rb') as f:
            self.walls_bank, self.walls_palette = bmp.load(f,
                bitmap=displayio.Bitmap, palette=displayio.Palette)
        self.walls_palette.make_transparent(15)
        with open("jumper-tiles.bmp", 'rb') as f:
            self.tiles_bank, self.tiles_palette = bmp.load(f,
                bitmap=displayio.Bitmap, palette=displayio.Palette)
        self.tiles_palette.make_transparent(15)

    def load_map(self, filename):
        with open(filename, 'rb') as f:
            self.level, palette = bmp.load(f, bitmap=displayio.Bitmap)

    def make_grids(self):
        self.back = displayio.TileGrid(self.tiles_bank,
            pixel_shader=self.tiles_palette, default_tile=0,
            width=10, height=8, tile_width=16, tile_height=16)
        self.walls = displayio.TileGrid(self.walls_bank,
            pixel_shader=self.walls_palette, default_tile=0,
            width=11, height=9, tile_width=16, tile_height=16)
        self.walls.x = -8
        self.walls.y = -8

    def fill_grids(self):
        for y in range(self.level.height + 1):
            self.walls[0, y] |= 1 | 4
            self.walls[self.level.width, y] |= 2 | 8
        for x in range(self.level.width + 1):
            self.walls[x, 0] |= 1 | 2
            self.walls[x, self.level.height] |= 4 | 8
        for y in range(self.level.height):
            for x in range(self.level.width):
                try:
                    tile = self.level[x ,y]
                except IndexError:
                    continue
                self.back[x, y] = tile
                if tile == 0:
                    self.walls[x, y] |= 8
                    self.walls[x + 1, y] |= 4
                    self.walls[x, y + 1] |= 2
                    self.walls[x + 1, y + 1] |= 1

    def tile(self, x, y):
        try:
            return self.level[x, y]
        except IndexError:
            return 0

class Sprite:
    def __init__(self, root):
        self.grid = displayio.TileGrid(level.tiles_bank,
            pixel_shader=level.tiles_palette, default_tile=4,
            tile_width=16, tile_height=16)
        root.append(self.grid)
        self.x = 0
        self.y = 0

    def move(self, x, y):
        self.grid.x = self.x = x
        self.grid.y = self.y = y

    def set_frame(self, frame, flip=False):
        self.grid[0, 0] = frame
        self.grid.flip_x = flip


class Hero(Sprite):
    def __init__(self, root, level):
        super().__init__(root)
        self.level = level
        self.move(16, 16)
        self.set_frame(0)
        self.dx = 1
        self.dy = 0
        self.dead = 0

    def update(self, frame):
        if self.dead:
            self.dead += 1
            if self.dead > 8:
                supervisor.reload()
            sprite.set_frame(8, frame // 4)
            return
        bottom_tile = self.level.tile((self.x + 8) // 16, (self.y + 16) // 16)
        if self.level.tile((self.x + 8) // 16, (self.y) // 16) == 0:
            self.dy = 0
        if bottom_tile not in (0, 2):
            self.dy = min(self.dy + 1, 6)
        elif bottom_tile == 2:
            self.dy = min(self.dy + 1, 0)
        else:
            self.dy = min(self.dy, 0)
        self.move(self.x, self.y + self.dy)
        while self.level.tile((self.x + 8) // 16, (self.y + 15) // 16) == 0:
            if self.y % 16 == 0:
                break
            self.move(self.x, self.y - 1)

        keys = buttons.get_pressed()
        if keys & buttons.K_RIGHT:
            self.dx = 1
            if self.level.tile((self.x + 13) // 16, (self.y + 10) // 16) != 0:
                self.move(self.x + 2, self.y)
            self.set_frame(5 + frame // 4)
        elif keys & buttons.K_LEFT:
            self.dx = -1
            if self.level.tile((self.x + 2) // 16, (self.y + 10) // 16) != 0:
                self.move(self.x - 2, self.y)
            self.set_frame(5 + frame // 4, True)
        elif keys & buttons.K_UP and self.level.tile((self.x + 8) // 16,
                                               (self.y + 15) // 16) == 2:
            self.move(self.x, self.y - 2)
            self.set_frame(7, frame // 4)
        elif keys & buttons.K_DOWN and bottom_tile == 2:
            self.move(self.x, self.y + 2)
            self.set_frame(7, frame // 4)
        else:
            self.set_frame(4, frame // 4)
        if keys & buttons.K_O and self.dy == 0 and bottom_tile in (0, 2):
            self.dy = -6
        if keys & buttons.K_X:
            if bolt.dx == 0:
                bolt.move(self.x + self.dx * 8, self.y)
                bolt.dx = self.dx * 6
            self.set_frame(10, (self.dx < 0))

    def kill(self):
        self.dead = 1


class Bolt(Sprite):
    def __init__(self, root, level):
        super().__init__(root)
        self.level = level
        self.set_frame(9)
        self.move(-16, -16)
        self.dx = 0

    def update(self, frame):
        if level.tile((self.x + 8) // 16, (self.y + 8) // 16) == 0:
            self.kill()
        else:
            self.set_frame(9, frame // 4)
            self.move(self.x + self.dx, self.y)

    def kill(self):
        self.dx = 0
        self.move(-16, -16)


class Sparky(Sprite):
    def __init__(self, root, level, x, y):
        super().__init__(root)
        self.level = level
        self.move(x, y)
        self.dead = False
        self.dx = 1

    def update(self, frame):
        if self.dead:
            if collide(self.x + 3, self.y + 1, self.x + 13, self.y + 15,
                       hero.x + 3, hero.y + 1, hero.x + 13, hero.y + 15):
                self.move(-16, -16)
            return
        sprite.set_frame(15, frame // 4)
        bottom_tile = self.level.tile((self.x + 8) // 16, (self.y + 16) // 16)
        forward_tile = self.level.tile((self.x + 8 + 8 * self.dx) // 16,
                                   (self.y + 8) // 16)
        if bottom_tile != 0 or forward_tile == 0:
            self.dx = -self.dx
        self.move(self.x + self.dx, self.y)
        if collide(self.x + 3, self.y + 1, self.x + 13, self.y + 15,
                   bolt.x + 8, bolt.y + 8):
            self.kill()
            bolt.kill()
        if collide(self.x + 3, self.y + 1, self.x + 13, self.y + 15,
                   hero.x + 3, hero.y + 1, hero.x + 13, hero.y + 15):
            hero.kill()

    def kill(self):
        self.dead = True
        sprite.set_frame(11 + (frame % 3))


display = board.DISPLAY
root = displayio.Group(max_size=8)
buttons = PyGamerButtons()
level = Level(root)
sprites = [
    Sparky(root, level, 104, 96),
    Sparky(root, level, 64, 32),
    Sparky(root, level, 16, 96),
    Sparky(root, level, 112, 16),
]
hero = Hero(root, level)
bolt = Bolt(root, level)
sprites.append(hero)
sprites.append(bolt)
display.show(root)
frame = 0

while True:
    frame = (frame + 1) % 8
    for sprite in sprites:
        sprite.update(frame)
    tick(12)
