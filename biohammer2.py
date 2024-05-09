import pygame as pg
import mido
from threading import Thread
from queue import Queue
from time import perf_counter_ns
from meatflower import MeatflowerGui, Cell, Text, EditableText, Row, Column, Table, Dropdown, Menu


class Editor:
    def __init__(self):
        pg.init()
        self.screen = pg.display.set_mode((1280, 720))
        self.gui = MeatflowerGui((1280,720))
        self.clock = pg.time.Clock()
        self.midi_out = mido.open_output()
        self.player_control = Queue()
        self.player_thread = Thread(target=self.player, args = [self.player_control], daemon = True).start()
    def edit(self, loop):
        title = self.gui.add_element(EditableText, (0,0), loop.title, colour = (0,0,0))
        length_value = self.gui.add_element(EditableText, (0,0), str(loop.length))
        length_control = self.gui.add_element(Row, (0,0), [self.gui.add_element(Text, (0,0), 'length:'), length_value], padding = 0)
        topbar = self.gui.add_element(Row, (0,0), [title, length_control])
        edit_table, delete_track_buttons = self.recalculate_edit_table(loop)
        play_button = self.gui.add_element(Text, (0,0), 'play >')
        instrument_menu = self.gui.add_element(Dropdown, (0,0), ['keyboard', 'drums'])
        add_track_button = self.gui.add_element(Text, (0,0), 'add track')
        bpm_value = self.gui.add_element(EditableText, (0,0), '120')
        bpm_control = self.gui.add_element(Row, (0,0), [self.gui.add_element(Text, (0,0), 'bpm:'), bpm_value], padding = 0)
        
        controls = self.gui.add_element(Row, (0,0), [play_button, instrument_menu, add_track_button, bpm_control])
        layout = self.gui.add_element(Column, (0,0), [topbar, edit_table, controls])

        self.player_control.put(['loop',loop])
        bpm = 0
        playing = False
        t = 0
        
        while True:
            try:
                new_bpm = int(bpm_value.text)
                if new_bpm != bpm:
                    bpm = new_bpm
                    self.player_control.put(['bpm', bpm])
                bpm_value.colour = (128,128,128)
            except:
                bpm_value.colour = (200,0,0)
            
            try:
                length = int(length_value.text)
                assert length > 0
                if length != loop.length:
                    loop.set_length(length)
                    self.gui.remove_element(edit_table)
                    edit_table, delete_track_buttons = self.recalculate_edit_table(loop)
                    layout.children[1] = edit_table
                length_value.colour = (128,128,128)
            except Exception as e:
                print(e)
                length_value.colour = (200,0,0)

            for event in pg.event.get():
                if event.type == pg.QUIT:
                    pg.quit()
                    return False
                elif event.type == pg.MOUSEBUTTONDOWN:                            
                    clicked_on = self.gui.at_point(event.pos)
                    ignored = 0 # keep track of Rows, Tables etc that we clicked in but don't do anything with
                    for elem in clicked_on:
                        if isinstance(elem, Cell) or isinstance(elem, EditableText):
                            self.gui.select_element(elem)
                            if elem in delete_track_buttons:
                                loop.delete_track(delete_track_buttons[elem])
                                self.gui.remove_element(edit_table)
                                edit_table, delete_track_buttons = self.recalculate_edit_table(loop)
                                layout.children[1] = edit_table
                        elif isinstance(elem, Dropdown):
                            if elem.selected:
                                elem.clicked(event.pos)
                            else:
                                self.gui.select_element(elem)
                        elif elem == play_button:
                            self.gui.select_element(None)
                            playing = not playing
                            self.player_control.put(['play' if playing else 'stop'])
                            play_button.set_text('pause ||' if playing else 'play >')
                        elif elem == add_track_button:
                            self.gui.select_element(None)
                            loop.add_track('new track')
                            self.gui.remove_element(edit_table)
                            edit_table, delete_track_buttons = self.recalculate_edit_table(loop)
                            layout.children[1] = edit_table
                        else:
                            ignored += 1
                    if ignored == len(clicked_on):
                        self.gui.select_element(None)
                elif event.type == pg.KEYDOWN:
                    self.gui.keypress(event)
            self.screen.blit(self.gui.render(),(0,0))
            if playing and loop.player_head >= 0:
                topcell = edit_table.children[(loop.player_head + 1, 0)].rect
                bottomcell = edit_table.children[(loop.player_head + 1, len(loop.events)-1)].rect
                pg.draw.line(self.screen, (250,250,250), topcell.midtop, bottomcell.midbottom, width=2)
            pg.display.flip()
            self.clock.tick()
    def recalculate_edit_table(self, loop):
        edit_table = self.gui.add_element(Table, (0,0), (loop.length + 2, len(loop.events)), padding=0.5)
        delete_track_buttons = {}
        y = 0
        for track in loop.events:
            edit_table.children[(0, y)] = self.gui.add_element(EditableText, (0,0), track)
            for x in range(loop.length):
                edit_table.children[(x+1, y)] = self.gui.add_element(Cell, (0,0), (30,30), str(loop.events[track][x].note if x in loop.events[track] else ''))
            btn = self.gui.add_element(Cell, (0,0), (30,30), 'X', colour = (200,200,200))
            edit_table.children[(loop.length+1, y)] = btn
            delete_track_buttons[btn] = track
            y += 1
        return edit_table, delete_track_buttons
    def player(self, q):
        playing = False
        loop = None
        ns_per_beat = 1000000000 # 1 second
        start_t = 0
        while True:
            if playing and (loop is not None):
                ns = perf_counter_ns()
                t = ns - start_t
                if t > ns_per_beat:
                    start_t = perf_counter_ns() - (t - ns_per_beat)
                    notes = loop.step()
                    for note in notes:
                        #msg = mido.Message('note_on', note = note)
                        self.midi_out.send(note)
                        #print(msg)
            if not q.empty():
                instruction = q.get()
                print(instruction)
                if instruction[0] == 'play':
                    playing = True
                    start_t = perf_counter_ns()
                elif instruction[0] == 'stop':
                    playing = False
                    if loop is not None:
                        loop.reset()
                elif instruction[0] == 'bpm':
                    ns_per_beat = (1/instruction[1])*60*1000000000
                    print(ns_per_beat)
                elif instruction[0] == 'loop':
                    loop = instruction[1]

class Loop:
    def __init__(self, length, tracks, title = None):
        self.length = length
        if title is None:
            self.title = "[loop]"
        else:
            self.title = title
        self.events = {}
        for track in tracks:
            self.add_track(track)
        self.reset()
    def events_at_time(self, t):
        return [self.events[track][t % self.length] for track in self.events if t % self.length in self.events[track]]
    def step(self):
        self.player_head = (self.player_head + 1) % self.length
        es = self.events_at_time(self.player_head)
        return es
    def set_length(self, l):
        self.length = l
        self.reset()
    def reset(self):
        self.player_head = -1
    def write(self, track, t, value):
        if value is None:
            self.events[track].pop(t, None)
        else:
            self.events[track][t] = mido.Message('note_on', note=int(value))
    def add_track(self, name):
        if name in self.events:
            self.add_track(name + '+')
        else:
            self.events[name] = {}
    def delete_track(self, track):
        self.events.pop(track)
        if len(self.events) == 0:
            self.add_track('new track') 

ed = Editor()
loop = Loop(10, ['a','hello'])
for i in range(10):
    loop.write('a',i,59)
for i in range(5):
    loop.write('hello',i*2,48)
#try:
ed.edit(loop)
#except Exception as e:
#    print(e)
#    pg.quit()

