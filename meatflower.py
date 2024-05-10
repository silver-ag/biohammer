# meatflower pygame gui system, built for the biohammer sequencer

import pygame as pg

class MeatflowerGui:
    def __init__(self, resolution, scale = 10, fontsize = 24):
        self.screen = pg.Surface(resolution)
        self.elements = []
        self.disabled_elements = []
        self.key_counter = 0
        self.selected_element = None
        self.font = pg.font.Font(None,fontsize)
        self.scale = scale
    def add_element(self, elem_type, *args, **kwargs):
        e = elem_type(*args, gui = self, **kwargs)
        self.elements.append(e)
        return e
    def remove_element(self, elem):
        if elem in self.elements:
            if self.selected_element == elem:
                self.selected_element = None
            self.elements.remove(elem)
            elem.destroy()
    def select_element(self, elem):
        if self.selected_element is not None:
            self.selected_element.deselect()
        self.selected_element = elem
        if elem is not None:
            self.selected_element.select()
    def disable_element(self, elem):
        if elem in self.elements:
            self.elements.remove(elem)
            self.disabled_elements.append(elem)
    def enable_element(self, elem):
        if elem in self.disabled_elements:
            self.disabled_elements.remove(elem)
            self.elements.append(elem)
    def render(self):
        self.screen.fill((0,0,0))
        for elem in self.elements:
            elem.draw(self.screen)
        return self.screen
    def at_point(self, point):
        r = []
        for elem in self.elements:
            if elem.rect.collidepoint(point):
                r.append(elem)
        return r
    def keypress(self, keyevent):
        if self.selected_element is not None:
            self.selected_element.keypress(keyevent)

class BaseGuiElement:
    def __init__(self, position, size, colour = (128,128,128), gui = None):
        self.rect = pg.Rect(position, size)
        self.colour = colour
        self.selected = False
        if gui is None:
            raise Exception("gui element must have a parent gui supplied")
        self.gui = gui
    def select(self):
        self.selected = True
    def deselect(self):
        self.selected = False
    def keypress(self, keyevent):
        pass
    def clicked(self, pos):
        pass
    def destroy(self):
        pass
    def enable(self):
        self.gui.enable_element(self)
    def disable(self):
        self.gui.disable_element(self)
    def draw(self, surface):
        pg.draw.rect(surface, self.colour, self.rect)
        pg.draw.line(surface, contrasting_colour(self.colour), self.rect.topleft, tuple_map(lambda a,b: a+b, self.rect.topleft, self.rect.size))
        pg.draw.line(surface, contrasting_colour(self.colour), (self.rect.x + self.rect.w, self.rect.y), (self.rect.x, self.rect.y + self.rect.h))


class Cell(BaseGuiElement):
    def __init__(self, position, size, label, colour = (128,128,128), gui = None):
        super().__init__(position, size, colour = colour, gui = gui)
        self.set_label(label)
    def set_label(self, text):
        self.label_img = self.gui.font.render(text, True, contrasting_colour(self.colour))
    def draw(self, surface):
        pg.draw.rect(surface, self.colour, pg.Rect(self.rect.topleft, self.rect.size))
        if self.selected:
            pg.draw.rect(surface, contrasting_colour(self.colour), pg.Rect(self.rect.topleft, self.rect.size), width = 2)
        surface.blit(self.label_img, tuple_map(lambda a,b:a-b, self.rect.center, self.label_img.get_rect().center))

class Text(BaseGuiElement):
    def __init__(self, position, text, colour = (128,128,128), gui = None):
        super().__init__(position, (0,0), colour = colour, gui = gui)
        self.set_text(text)
    def set_text(self, text):
        self.text_img = self.gui.font.render(text, True, contrasting_colour(self.colour))
        self.rect.size = tuple_map(lambda a,b: a+b, self.text_img.get_size(), (self.gui.scale, self.gui.scale))
        self.text = text
    def draw(self, surface):
        pg.draw.rect(surface, self.colour, pg.Rect(self.rect.topleft, self.rect.size))
        surface.blit(self.text_img, tuple_map(lambda a,b:a-b, self.rect.center, self.text_img.get_rect().center))

class EditableText(BaseGuiElement):
    def __init__(self, position, default, colour = (128,128,128), gui = None):
        super().__init__(position, (0,0), colour = colour, gui = gui)
        self.set_text(default)
        self.cursor = len(self.text)
    def set_text(self, text):
        self.text_img = self.gui.font.render(text, True, contrasting_colour(self.colour))
        self.rect.size = tuple_map(lambda a,b: a+b, self.text_img.get_size(), (self.gui.scale, self.gui.scale))
        self.text = text
    def draw(self, surface):
        pg.draw.rect(surface, self.colour, pg.Rect(self.rect.topleft, self.rect.size))
        text_position = tuple_map(lambda a,b:a-b, self.rect.center, self.text_img.get_rect().center)
        surface.blit(self.text_img, text_position)
        if self.selected:
            text_size = self.gui.font.size(self.text[:self.cursor])
            pg.draw.line(surface, contrasting_colour(self.colour),
                         (text_position[0] + text_size[0], text_position[1]),
                         (text_position[0] + text_size[0], text_position[1] + text_size[1]))
    def keypress(self, event):
        if event.type == pg.KEYDOWN:
            if event.key == pg.K_LEFT:
                if self.cursor > 0:
                    self.cursor -= 1
            elif event.key == pg.K_RIGHT:
                if self.cursor < len(self.text):
                    self.cursor += 1
            elif event.key == pg.K_UP:
                self.cursor = len(self.text)
            elif event.key == pg.K_DOWN:
                self.cursor = 0
            elif event.key == pg.K_DELETE:
                self.set_text(self.text[:self.cursor] + self.text[self.cursor+1:])
            elif event.key == pg.K_BACKSPACE:
                self.set_text(self.text[:self.cursor-1] + self.text[self.cursor:])
                if self.cursor > 0:
                    self.cursor -= 1
            elif event.key == pg.K_RETURN:
                self.gui.select_element(None)
            else:
                self.set_text(self.text[:self.cursor] + event.unicode + self.text[self.cursor:])
                self.cursor += len(event.unicode)

class Row(BaseGuiElement):
    def __init__(self, position, children = [], padding = 1, colour = (0,0,0), gui = None):
        super().__init__(position, (0,0), colour = colour, gui = gui)
        self.children = children
        self.padding = self.gui.scale * padding
    def destroy(self):
        for child in self.children.values():
            self.gui.remove_element(child)
    def draw(self, surface):
        xpos = self.padding
        self.rect.h = 0
        for child in self.children:
            child.rect.x = self.rect.x + xpos
            child.rect.y = self.rect.y
            xpos += child.rect.w
            xpos += self.padding
            if child.rect.h > self.rect.h:
                self.rect.h = child.rect.h
        self.rect.w = xpos

class Column(BaseGuiElement):
    def __init__(self, position, children = [], padding = 1, colour = (0,0,0), gui = None):
        super().__init__(position, (0,0), colour = colour, gui = gui)
        self.children = children
        self.padding = self.gui.scale * padding
    def destroy(self):
        for child in self.children.values():
            self.gui.remove_element(child)
    def draw(self, surface):
        ypos = self.padding
        self.rect.w = 0
        for child in self.children:
            child.rect.x = self.rect.x
            child.rect.y = self.rect.y + ypos
            ypos += child.rect.h
            ypos += self.padding
            if child.rect.w > self.rect.w:
                self.rect.w = child.rect.w
        self.rect.h = ypos

class Table(BaseGuiElement):
    def __init__(self, position, table_size, children = None, padding = 1, colour = (0,0,0), gui = None):
        super().__init__(position, (0,0), colour = colour, gui = gui)
        self.table_size = table_size # tuple, (cols, rows)
        if children is None:
            self.children = {} # {(x,y): elem}
        else:
            self.children = children
        self.padding = self.gui.scale * padding
    def destroy(self):
        for child in self.children.values():
            self.gui.remove_element(child)
    def draw(self, surface):
        cols = [0] * self.table_size[0]
        rows = [0] * self.table_size[1]
        for (x,y),child in self.children.items():
            if cols[x] < child.rect.w + self.padding:
                cols[x] = child.rect.w + self.padding
            if rows[y] < child.rect.h + self.padding:
                rows[y] = child.rect.h + self.padding
        for (x,y),child in self.children.items():
            child.rect.x = self.rect.x + sum(cols[:x]) + (x*self.padding)
            child.rect.y = self.rect.y + sum(rows[:y]) + (y*self.padding)
        self.rect.w = sum(cols) + ((len(cols)-1)*self.padding)
        self.rect.h = sum(rows) + ((len(rows)-1)*self.padding)


class Menu(BaseGuiElement):
    def __init__(self, position, options, colour = (128,128,128), gui = None):
        super().__init__(position, (0,0), colour = colour, gui = gui)
        self.options = {option: self.gui.font.render(option, True, contrasting_colour(self.colour)) for option in options}
        self.rect.w = max([option.get_size()[0] for option in self.options.values()])
        self.rect.h = sum([option.get_size()[1] for option in self.options.values()])
    def clicked(self, pos):
        ypos = 0
        for text,option in self.options.items():
            option_rect = option.get_rect()
            if pg.Rect(option_rect.topleft, (self.rect.w, option_rect.h)).collidepoint(pos):
                return text
            ypos += option_rect.h
        return None
    def draw(self, surface):
        pg.draw.rect(surface, self.colour, self.rect)
        ypos = 0
        for option in self.options.values():
            surface.blit(option, (self.rect.x, self.rect.y + ypos))
            ypos += option.get_size()[1]


class Dropdown(BaseGuiElement):
    def __init__(self, position, options, colour = (128,128,128), gui = None):
        super().__init__(position, (0,0), colour = colour, gui = gui)
        self.value = options[0]
        self.options = {option: self.gui.font.render(option, True, contrasting_colour(self.colour)) for option in options}
        self.rect.size = tuple_map(lambda a,b: a+b, self.gui.font.size(self.value), (self.gui.scale, self.gui.scale))
    def select(self):
        super().select()
        self.rect.w = max([option.get_size()[0] for option in self.options.values()])
        self.rect.h = sum([option.get_size()[1] for option in self.options.values()])
    def deselect(self):
        super().deselect()
        self.rect.size = tuple_map(lambda a,b: a+b, self.gui.font.size(self.value), (self.gui.scale, self.gui.scale))
    def clicked(self, pos):
        ypos = 0
        for text,option in self.options.items():
            option_rect = option.get_rect()
            if pg.Rect((self.rect.x, self.rect.y + ypos), (self.rect.w, option_rect.h)).collidepoint(pos):
                self.value = text
            ypos += option_rect.h
        self.deselect()
    def draw(self, surface):
        pg.draw.rect(surface, self.colour, self.rect)
        if self.selected:
            ypos = 0
            for option in self.options.values():
                surface.blit(option, (self.rect.x, self.rect.y + ypos))
                ypos += option.get_size()[1]
        else:
            surface.blit(self.options[self.value], tuple_map(lambda a,b:a-b, self.rect.center, self.options[self.value].get_rect().center))
    

# utilities

def contrasting_colour(bg):
    # choose a good foreground colour to stand out on the given background (or vice versa)
    brightness = (bg[0] * 0.299) + (bg[1] * 0.587) + (bg[2] * 0.114) # different colours are perceived as having different brightnesses because of how the eye works
    if brightness > 186: # middle value 186 not 128 because of brightness adjustment in most screens
        return (0,0,0)
    else:
        return (255,255,255)

def tuple_map(operator, a, b):
    return tuple(map(operator, a, b))
