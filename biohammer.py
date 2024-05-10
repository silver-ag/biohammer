# gui
import pygame as pg
from meatflower import MeatflowerGui, Cell, Text, EditableText, Row, Column, Table, Dropdown, Menu

# midi
import rtmidi
from rtmidi.midiconstants import NOTE_ON, NOTE_OFF

# sequencing
import sched
import time
from threading import Thread

# saving
import json
from plyer import filechooser

class Editor:
    def __init__(self):
        pg.init()
        self.screen = pg.display.set_mode((1280, 720))
        self.gui = MeatflowerGui((1280,720))
        self.clock = pg.time.Clock()
        self.midi_out = rtmidi.MidiOut()
        self.set_midi_port(0)
        self.midi_out.set_port_name("biohammer")
        self.scheduler = sched.scheduler(time.time, time.sleep)
        self.scheduler_thread = Thread(target=self.run_scheduler,daemon=True).start()
        # annotate the scheduler with some extra data we'll use to account for the loop times being in logical format unaware of their bpm
        self.scheduler.start_t = 0
        self.scheduler.scheduled_up_to = 0
        self.scheduler.scheduler_cursor = 1
    def run_scheduler(self):
        while True:
            self.scheduler.run()
    def clear_schedule(self):
        for event in self.scheduler.queue:
            self.scheduler.cancel(event)
        self.scheduler = sched.scheduler(time.time, time.sleep)
        self.scheduler_thread = Thread(target=self.run_scheduler,daemon=True).start()
        self.scheduler.start_t = time.time()
        self.scheduler.scheduled_up_to = self.scheduler.start_t
        self.scheduler.scheduler_cursor = 0
    def set_midi_port(self, index):
        self.midi_out.close_port()
        self.midi_out_port = self.midi_out.open_port(index)
        self.midi_out_name = self.midi_out.get_ports()[index]
    def edit(self, loop = None):
        if loop is None:
            loop = Loop(8,['track 1'])
        title = self.gui.add_element(EditableText, (0,0), loop.title, colour = (0,0,0))
        length_value = self.gui.add_element(EditableText, (0,0), str(loop.length))
        length_control = self.gui.add_element(Row, (0,0), [self.gui.add_element(Text, (0,0), 'length:'), length_value], padding = 0)
        midiout_control = self.gui.add_element(Dropdown, (0,0), self.midi_out.get_ports())
        save_button = self.gui.add_element(Text, (0,0), 'save')
        load_button = self.gui.add_element(Text, (0,0), 'load')
        topbar = self.gui.add_element(Row, (0,0), [title, length_control, midiout_control, save_button, load_button])
        edit_table, delete_track_buttons = self.recalculate_edit_table(loop)
        play_button = self.gui.add_element(Text, (0,0), 'play >')
        octave_value = self.gui.add_element(EditableText, (0,0), '4')
        octave_control = self.gui.add_element(Row, (0,0), [self.gui.add_element(Text, (0,0), 'octave:'), octave_value], padding = 0)
        add_track_button = self.gui.add_element(Text, (0,0), 'add track')
        bpm_value = self.gui.add_element(EditableText, (0,0), '120')
        bpm_control = self.gui.add_element(Row, (0,0), [self.gui.add_element(Text, (0,0), 'bpm:'), bpm_value], padding = 0)
        
        controls = self.gui.add_element(Row, (0,0), [play_button, octave_control, add_track_button, bpm_control])
        layout = self.gui.add_element(Column, (0,0), [topbar, edit_table, controls])

        _screen_size = self.gui.screen.get_size()
        save_alert = self.gui.add_element(Cell, ((_screen_size[0]/2)-250,(_screen_size[1]/2)-50), (500,100), 'you have unsaved work, save first if you want to keep it')
        save_alert.disable()
        def save_deselect():
            save_alert.selected = False
            save_alert.disable()
        save_alert.deselect = save_deselect

        bpm = 0
        playing = False
        octave = 4
        latest_saved = ''
        self.scheduler.start_t = 0
        self.scheduler.scheduled_up_to = 0
        self.scheduler.scheduler_cursor = 1
        
        while True:
            try:
                new_bpm = int(bpm_value.text)
                if new_bpm != bpm:
                    bpm = new_bpm
                    self.clear_schedule()
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

            if midiout_control.value != self.midi_out_name:
                available_ports = self.midi_out.get_ports()
                self.set_midi_port(available_ports.index(midiout_control.value) if midiout_control.value in available_ports else 0)

            try:
                octave = int(octave_value.text)
                octave_value.colour = (128,128,128)
            except:
                octave_value.colour = (200,0,0)

            t = time.time()
            if playing and self.scheduler.scheduled_up_to < t + 2:
                for i in range(10):
                    notes = loop.events_at_time(self.scheduler.scheduler_cursor)
                    s_t = 0
                    for note in notes:
                        s_t = self.scheduler.start_t + (self.scheduler.scheduler_cursor * (60/bpm if bpm > 0 else 1))
                        self.scheduler.enterabs(s_t, 0, self.midi_out.send_message, argument=([NOTE_ON,note,127],))
                    self.scheduler.scheduled_up_to = s_t
                    self.scheduler.scheduler_cursor += 1
                

            for event in pg.event.get():
                if event.type == pg.QUIT:
                    if loop.serialise() != latest_saved and not save_alert.selected:
                        save_alert.enable()
                        self.gui.select_element(save_alert)
                    else:
                        pg.quit()
                        return False
                elif event.type == pg.MOUSEBUTTONDOWN:
                    clicked_on = self.gui.at_point(event.pos)
                    ignored = 0 # keep track of Rows, Tables etc that we clicked in but don't do anything with
                    for elem in clicked_on:
                        if isinstance(elem, NoteCell) or isinstance(elem, EditableText):
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
                            self.clear_schedule()
                            play_button.set_text('pause ||' if playing else 'play >')
                        elif elem == add_track_button:
                            self.gui.select_element(None)
                            loop.add_track('new track')
                            self.gui.remove_element(edit_table)
                            edit_table, delete_track_buttons = self.recalculate_edit_table(loop)
                            layout.children[1] = edit_table
                        elif elem == save_button:
                            filename = filechooser.save_file()[0]
                            if filename is not None:
                                if '.' not in filename:
                                    filename += '.bhmr'
                                with open(filename, 'w+') as file:
                                    latest_saved = str(loop.serialise())
                                    file.write(latest_saved)
                        elif elem == load_button:
                            filename = filechooser.open_file()[0]
                            if filename is not None:
                                with open(filename, 'r') as file:
                                    data = json.loads(file.read())
                                    loop = Loop.from_data(data)
                                    self.gui.remove_element(edit_table)
                                    edit_table, delete_track_buttons = self.recalculate_edit_table(loop)
                                    layout.children[1] = edit_table
                        else:
                            ignored += 1
                    if ignored == len(clicked_on):
                        self.gui.select_element(None)
                elif event.type == pg.KEYDOWN:
                    if self.gui.selected_element is None and event.unicode in '1234567890':
                        octave_value.set_text(event.unicode)
                    if isinstance(self.gui.selected_element, NoteCell):
                        # capitals are sharps, so shift-c is C# but shift-e if F
                        notes = {'c': 0, 'C': 1, 'd': 2, 'D': 3, 'e': 4, 'E': 5, 'f': 5, 'F': 6, 'g': 7, 'G': 8, 'a': 9, 'A': 10, 'b': 11, 'B': 0}
                        if event.unicode in notes:
                            self.gui.selected_element.set_value(notes[event.unicode] + (12*octave))
                            loop.write(self.gui.selected_element.track, self.gui.selected_element.index, self.gui.selected_element.value)
                    else:
                        self.gui.keypress(event)
            self.screen.blit(self.gui.render(),(0,0))
            if playing and loop.player_head >= 0:
                topcell = edit_table.children[(loop.player_head + 1, 0)].rect
                bottomcell = edit_table.children[(loop.player_head + 1, len(loop.events)-1)].rect
                pg.draw.line(self.screen, (250,250,250), topcell.midtop, bottomcell.midbottom, width=2)
            pg.display.flip()
            self.clock.tick(60)
    def recalculate_edit_table(self, loop):
        edit_table = self.gui.add_element(Table, (0,0), (loop.length + 2, len(loop.events)), padding=0.5)
        delete_track_buttons = {}
        y = 0
        for track in loop.events:
            edit_table.children[(0, y)] = self.gui.add_element(EditableText, (0,0), track)
            for x in range(loop.length):
                edit_table.children[(x+1, y)] = self.gui.add_element(NoteCell, (0,0), (30,30), loop.events[track][x] if x in loop.events[track] else None)
                # add some supplementary data
                edit_table.children[(x+1, y)].track = track
                edit_table.children[(x+1, y)].index = x
            btn = self.gui.add_element(Cell, (0,0), (30,30), 'X', colour = (200,200,200))
            edit_table.children[(loop.length+1, y)] = btn
            delete_track_buttons[btn] = track
            y += 1
        return edit_table, delete_track_buttons

class NoteCell(Cell):
    def __init__(self, position, size, value, colour = (128,128,128), gui = None):
        super().__init__(position, size, '', colour = colour, gui = gui)
        self.set_value(value)
    def set_value(self, value):
        self.value = value
        self.set_label(self.midinum_to_name(value))
    def midinum_to_name(self, n):
        if n is None:
            return ''
        else:
            octave = n // 12
            note = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B'][n % 12]
            return f'{note}{octave}'

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
            self.events[track][t] = int(value)
    def add_track(self, name):
        if name in self.events:
            self.add_track(name + '+')
        else:
            self.events[name] = {}
    def delete_track(self, track):
        self.events.pop(track)
        if len(self.events) == 0:
            self.add_track('new track')
    def serialise(self):
        # for saving purposes
        return json.dumps({'title': self.title, 'length': self.length, 'tracks': self.events})
    def from_data(data):
        new_loop = Loop(data['length'], data['tracks'], title = data['title'])
        for track in data['tracks']:
            for index in data['tracks'][track]:
                new_loop.write(track, int(index), data['tracks'][track][index])
        print(new_loop.events)
        return new_loop
        

ed = Editor()

try:
    ed.edit()
except Exception as e:
    print(repr(e))
    pg.quit()

