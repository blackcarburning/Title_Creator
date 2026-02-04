import tkinter as tk
from tkinter import ttk, font, colorchooser, filedialog
from PIL import Image, ImageDraw, ImageFont, ImageGrab
import os
import json
import math
import wave
import struct
import threading

# Try to import audio playback libraries
try:
    import winsound
    HAS_WINSOUND = True
except ImportError:
    HAS_WINSOUND = False

try:
    import simpleaudio as sa
    HAS_SIMPLEAUDIO = True
except ImportError:
    HAS_SIMPLEAUDIO = False


# International Morse Code reference
MORSE_CODE = {
    'A': '.-', 'B': '-...', 'C': '-.-.', 'D': '-..', 'E': '.', 'F': '..-.',
    'G': '--.', 'H': '....', 'I': '..', 'J': '.---', 'K': '-.-', 'L': '.-..',
    'M': '--', 'N': '-.', 'O': '---', 'P': '.--.', 'Q': '--.-', 'R': '.-.',
    'S': '...', 'T': '-', 'U': '..-', 'V': '...-', 'W': '.--', 'X': '-..-',
    'Y': '-.--', 'Z': '--..',
    '0': '-----', '1': '.----', '2': '..---', '3': '...--', '4': '....-',
    '5': '.....', '6': '-....', '7': '--...', '8': '---..', '9': '----.',
    '.': '.-.-.-', ',': '--..--', '?': '..--..', "'": '.----.', '!': '-.-.--',
    '/': '-..-.', '(': '-.--.', ')': '-.--.-', '&': '.-...', ':': '---...',
    ';': '-.-.-.', '=': '-...-', '+': '.-.-.', '-': '-....-', '_': '..--.-',
    '"': '.-..-.', '$': '...-..-', '@': '.--.-.'
}

# Reverse mapping for Morse to text
MORSE_TO_TEXT = {v: k for k, v in MORSE_CODE.items()}

def text_to_morse(text):
    """Convert text to Morse code. Words separated by /"""
    result = []
    for word in text.upper().split():
        morse_word = []
        for char in word:
            if char in MORSE_CODE:
                morse_word.append(MORSE_CODE[char])
        if morse_word:
            result.append(' '.join(morse_word))
    return ' / '.join(result)

def morse_to_text(morse):
    """Convert Morse code to text. Words separated by /"""
    result = []
    words = morse.strip().split(' / ')
    for word in words:
        text_word = []
        chars = word.strip().split()
        for char in chars:
            char = char.strip()
            if char in MORSE_TO_TEXT:
                text_word.append(MORSE_TO_TEXT[char])
            elif char:
                text_word.append('?')
        if text_word:
            result.append(''.join(text_word))
    return ' '.join(result)


class MorseAudioGenerator:
    """Generate Morse code audio signals""" 
    
    def __init__(self, frequency=700, wpm=20, sample_rate=44100):
        self.frequency = frequency  # Tone frequency in Hz (standard: 600-800 Hz)
        self.wpm = wpm  # Words per minute
        self.sample_rate = sample_rate
        
        # Calculate timing based on WPM
        # Standard word "PARIS" = 50 time units
        # At 20 WPM: 1 unit = 60ms
        self.dit_duration = 1.2 / wpm  # Duration of a dit in seconds
        self.dah_duration = self.dit_duration * 3
        self.element_space = self.dit_duration  # Space between elements
        self.letter_space = self.dit_duration * 3  # Space between letters
        self.word_space = self.dit_duration * 7  # Space between words
    
    def generate_tone(self, duration):
        """Generate a sine wave tone"""
        num_samples = int(self.sample_rate * duration)
        samples = []
        for i in range(num_samples):
            # Apply envelope to reduce clicks
            t = i / self.sample_rate
            envelope = 1.0
            fade_time = 0.005  # 5ms fade
            if t < fade_time:
                envelope = t / fade_time
            elif t > duration - fade_time:
                envelope = (duration - t) / fade_time
            
            sample = envelope * math.sin(2 * math.pi * self.frequency * t)
            samples.append(sample)
        return samples
    
    def generate_silence(self, duration):
        """Generate silence"""
        num_samples = int(self.sample_rate * duration)
        return [0.0] * num_samples
    
    def morse_to_audio_samples(self, morse_code):
        """Convert Morse code string to audio samples"""
        samples = []
        
        i = 0
        while i < len(morse_code):
            char = morse_code[i]
            
            if char == '.':
                samples.extend(self.generate_tone(self.dit_duration))
                # Add element space if next char is part of same letter
                if i + 1 < len(morse_code) and morse_code[i + 1] in '.-':
                    samples.extend(self.generate_silence(self.element_space))
            elif char == '-':
                samples.extend(self.generate_tone(self.dah_duration))
                # Add element space if next char is part of same letter
                if i + 1 < len(morse_code) and morse_code[i + 1] in '.-':
                    samples.extend(self.generate_silence(self.element_space))
            elif char == ' ':
                # Check for word separator " / "
                if i + 2 < len(morse_code) and morse_code[i:i+3] == ' / ':
                    samples.extend(self.generate_silence(self.word_space))
                    i += 2  # Skip the " / "
                else:
                    # Space between letters
                    samples.extend(self.generate_silence(self.letter_space))
            elif char == '/':
                # Word separator (handled above with spaces)
                pass
            
            i += 1
        
        return samples
    
    def samples_to_wav_data(self, samples):
        """Convert samples to WAV byte data"""
        # Normalize and convert to 16-bit integers
        max_val = max(abs(s) for s in samples) if samples else 1
        if max_val == 0:
            max_val = 1
        
        audio_data = b''
        for sample in samples:
            normalized = int((sample / max_val) * 32767 * 0.8)  # 80% volume
            audio_data += struct.pack('<h', normalized)
        
        return audio_data
    
    def save_wav(self, morse_code, filename):
        """Save Morse code audio to WAV file"""
        samples = self.morse_to_audio_samples(morse_code)
        audio_data = self.samples_to_wav_data(samples)
        
        with wave.open(filename, 'w') as wav_file:
            wav_file.setnchannels(1)  # Mono
            wav_file.setsampwidth(2)  # 16-bit
            wav_file.setframerate(self.sample_rate)
            wav_file.writeframes(audio_data)
    
    def play_morse(self, morse_code, temp_file=None):
        """Play Morse code audio"""
        samples = self.morse_to_audio_samples(morse_code)
        audio_data = self.samples_to_wav_data(samples)
        
        if HAS_SIMPLEAUDIO:
            # Use simpleaudio if available
            wave_obj = sa.WaveObject(audio_data, 1, 2, self.sample_rate)
            play_obj = wave_obj.play()
            play_obj.wait_done()
        elif HAS_WINSOUND and temp_file:
            # Use winsound on Windows
            self.save_wav(morse_code, temp_file)
            winsound.PlaySound(temp_file, winsound.SND_FILENAME)
            try:
                os.remove(temp_file)
            except:
                pass
        else:
            # Fallback: save to temp file and try to play
            if temp_file:
                self.save_wav(morse_code, temp_file)
                return temp_file
        return None


class TextOverlayApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Text Overlay Creator")
        self.root.geometry("1200x900")
        
        self.config_file = os.path.join(os.path.expanduser("~"), ".text_overlay_config.json")
        
        # Text properties
        self.text_content = "Double-click to edit\nLine 2\nLine 3"
        self.font_family = "Arial"
        self.font_size = 72
        self.font_color = "#FFFFFF"
        self.text_x = 960
        self.text_y = 540
        self.flip_h = False
        self.vertical_stack = False
        self.text_align = "center"
        self.line_spacing = 1.0
        
        # Morse audio settings
        self.morse_frequency = 700  # Hz
        self.morse_wpm = 20  # Words per minute
        self.morse_generator = MorseAudioGenerator(self.morse_frequency, self.morse_wpm)
        self.is_playing = False
        
        # Load saved settings
        self.load_config()
        
        # Canvas scaling
        self.scale = 1.0
        self.canvas_width = 1920
        self.canvas_height = 1080
        
        # Dragging state
        self.dragging = False
        self.resizing = False
        self.drag_start_x = 0
        self.drag_start_y = 0
        self.resize_handle = None
        
        # Dropper state
        self.dropper_active = False
        
        self.setup_ui()
        self.root.bind("<Configure>", self.on_resize)
        self.root.after(100, self.fit_canvas)
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        
    def load_config(self):
        """Load saved configuration"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    config = json.load(f)
                    self.font_family = config.get('font_family', self.font_family)
                    self.font_size = config.get('font_size', self.font_size)
                    self.font_color = config.get('font_color', self.font_color)
                    self.text_align = config.get('text_align', self.text_align)
                    self.line_spacing = config.get('line_spacing', self.line_spacing)
                    self.morse_frequency = config.get('morse_frequency', self.morse_frequency)
                    self.morse_wpm = config.get('morse_wpm', self.morse_wpm)
                    self.morse_generator = MorseAudioGenerator(self.morse_frequency, self.morse_wpm)
        except:
            pass
            
    def save_config(self):
        """Save configuration"""
        try:
            config = {
                'font_family': self.font_family,
                'font_size': self.font_size,
                'font_color': self.font_color,
                'text_align': self.text_align,
                'line_spacing': self.line_spacing,
                'morse_frequency': self.morse_frequency,
                'morse_wpm': self.morse_wpm
            }
            with open(self.config_file, 'w') as f:
                json.dump(config, f)
        except:
            pass
            
    def on_close(self):
        """Handle window close"""
        self.save_config()
        self.root.destroy()
        
    def setup_ui(self):
        # Main container
        main = ttk.Frame(self.root, padding="5")
        main.pack(fill=tk.BOTH, expand=True)
        
        # Control panel
        controls = ttk.LabelFrame(main, text="Controls", padding="10")
        controls.pack(fill=tk.X, pady=(0, 5))
        
        # Row 1: Font selection
        row1 = ttk.Frame(controls)
        row1.pack(fill=tk.X, pady=2)
        
        ttk.Label(row1, text="Font:").pack(side=tk.LEFT, padx=(0, 5))
        
        available_fonts = sorted(list(font.families()))
        self.font_var = tk.StringVar(value=self.font_family)
        font_combo = ttk.Combobox(row1, textvariable=self.font_var, values=available_fonts, width=25)
        font_combo.pack(side=tk.LEFT, padx=5)
        font_combo.bind("<<ComboboxSelected>>", lambda e: self.on_font_change())
        
        ttk.Label(row1, text="Size:").pack(side=tk.LEFT, padx=(15, 5))
        self.size_var = tk.IntVar(value=self.font_size)
        size_spin = ttk.Spinbox(row1, from_=8, to=500, textvariable=self.size_var, width=5, command=self.on_size_change)
        size_spin.pack(side=tk.LEFT, padx=5)
        size_spin.bind("<Return>", lambda e: self.on_size_change())
        
        ttk.Label(row1, text="Color:").pack(side=tk.LEFT, padx=(15, 5))
        self.color_btn = tk.Button(row1, width=4, bg=self.font_color, command=self.pick_color)
        self.color_btn.pack(side=tk.LEFT, padx=5)
        
        self.dropper_btn = tk.Button(row1, text="Dropper", command=self.activate_dropper, width=7)
        self.dropper_btn.pack(side=tk.LEFT, padx=5)
        
        tk.Button(row1, text="Export PNG", command=self.export_png, font=("Arial", 10, "bold"), 
                  bg="#4CAF50", fg="white", width=10).pack(side=tk.RIGHT, padx=5)
        
        # Row 2: Alignment, spacing, flip options
        row2 = ttk.Frame(controls)
        row2.pack(fill=tk.X, pady=2)
        
        ttk.Label(row2, text="Align:").pack(side=tk.LEFT, padx=(0, 5))
        self.align_var = tk.StringVar(value=self.text_align)
        align_frame = ttk.Frame(row2)
        align_frame.pack(side=tk.LEFT, padx=5)
        
        self.align_left_btn = tk.Button(align_frame, text="◀", width=3, command=lambda: self.set_align("left"))
        self.align_left_btn.pack(side=tk.LEFT)
        self.align_center_btn = tk.Button(align_frame, text="●", width=3, command=lambda: self.set_align("center"))
        self.align_center_btn.pack(side=tk.LEFT)
        self.align_right_btn = tk.Button(align_frame, text="▶", width=3, command=lambda: self.set_align("right"))
        self.align_right_btn.pack(side=tk.LEFT)
        self.update_align_buttons()
        
        ttk.Label(row2, text="Line Spacing:").pack(side=tk.LEFT, padx=(15, 5))
        self.spacing_var = tk.DoubleVar(value=self.line_spacing)
        spacing_spin = ttk.Spinbox(row2, from_=0.5, to=3.0, increment=0.1, textvariable=self.spacing_var, width=5, command=self.on_spacing_change)
        spacing_spin.pack(side=tk.LEFT, padx=5)
        spacing_spin.bind("<Return>", lambda e: self.on_spacing_change())
        
        ttk.Separator(row2, orient=tk.VERTICAL).pack(side=tk.LEFT, padx=15, fill=tk.Y)
        
        self.flip_h_btn = tk.Button(row2, text="Flip H", command=self.toggle_flip_h, width=6)
        self.flip_h_btn.pack(side=tk.LEFT, padx=5)
        
        self.vertical_btn = tk.Button(row2, text="Vertical", command=self.toggle_vertical, width=7)
        self.vertical_btn.pack(side=tk.LEFT, padx=5)
        
        ttk.Button(row2, text="Center", command=self.center_text).pack(side=tk.LEFT, padx=15)
        
        # Morse code buttons
        ttk.Separator(row2, orient=tk.VERTICAL).pack(side=tk.LEFT, padx=15, fill=tk.Y)
        
        tk.Button(row2, text="Text→Morse", command=self.convert_to_morse, width=10, 
                  bg="#2196F3", fg="white").pack(side=tk.LEFT, padx=5)
        tk.Button(row2, text="Morse→Text", command=self.convert_from_morse, width=10,
                  bg="#FF9800", fg="white").pack(side=tk.LEFT, padx=5)
        
        # Row 3: Text input (multi-line)
        row3 = ttk.Frame(controls)
        row3.pack(fill=tk.X, pady=5)
        
        ttk.Label(row3, text="Text:").pack(side=tk.LEFT, padx=(0, 5), anchor=tk.N)
        
        text_frame = ttk.Frame(row3)
        text_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        self.text_entry = tk.Text(text_frame, height=4, width=80, wrap=tk.WORD)
        self.text_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.text_entry.insert("1.0", self.text_content)
        self.text_entry.bind("<KeyRelease>", lambda e: self.on_text_change())
        
        scrollbar = ttk.Scrollbar(text_frame, orient=tk.VERTICAL, command=self.text_entry.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.text_entry.config(yscrollcommand=scrollbar.set)
        
        # Row 4: Position info
        row4 = ttk.Frame(controls)
        row4.pack(fill=tk.X, pady=2)
        
        self.pos_var = tk.StringVar(value=f"Position: X={self.text_x}, Y={self.text_y}")
        ttk.Label(row4, textvariable=self.pos_var).pack(side=tk.LEFT)
        
        self.dropper_status = tk.StringVar(value="")
        ttk.Label(row4, textvariable=self.dropper_status, foreground="blue").pack(side=tk.RIGHT)
        
        # Morse Audio Section
        morse_frame = ttk.LabelFrame(main, text="Morse Code Audio", padding="10")
        morse_frame.pack(fill=tk.X, pady=(0, 5))
        
        # Morse input row
        morse_row1 = ttk.Frame(morse_frame)
        morse_row1.pack(fill=tk.X, pady=2)
        
        ttk.Label(morse_row1, text="Morse Code:").pack(side=tk.LEFT, padx=(0, 5))
        
        self.morse_entry = tk.Entry(morse_row1, width=60)
        self.morse_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        self.morse_entry.insert(0, "... --- ...")  # Default: SOS
        
        # Audio settings row
        morse_row2 = ttk.Frame(morse_frame)
        morse_row2.pack(fill=tk.X, pady=5)
        
        ttk.Label(morse_row2, text="Frequency (Hz):").pack(side=tk.LEFT, padx=(0, 5))
        self.freq_var = tk.IntVar(value=self.morse_frequency)
        freq_spin = ttk.Spinbox(morse_row2, from_=300, to=1200, textvariable=self.freq_var, width=6, command=self.on_freq_change)
        freq_spin.pack(side=tk.LEFT, padx=5)
        freq_spin.bind("<Return>", lambda e: self.on_freq_change())
        
        ttk.Label(morse_row2, text="WPM:").pack(side=tk.LEFT, padx=(15, 5))
        self.wpm_var = tk.IntVar(value=self.morse_wpm)
        wpm_spin = ttk.Spinbox(morse_row2, from_=5, to=40, textvariable=self.wpm_var, width=4, command=self.on_wpm_change)
        wpm_spin.pack(side=tk.LEFT, padx=5)
        wpm_spin.bind("<Return>", lambda e: self.on_wpm_change())
        
        ttk.Separator(morse_row2, orient=tk.VERTICAL).pack(side=tk.LEFT, padx=15, fill=tk.Y)
        
        self.play_btn = tk.Button(morse_row2, text="▶ Play", command=self.play_morse_audio, width=8,
                                   bg="#4CAF50", fg="white", font=("Arial", 10, "bold"))
        self.play_btn.pack(side=tk.LEFT, padx=5)
        
        tk.Button(morse_row2, text="💾 Export WAV", command=self.export_morse_wav, width=12,
                  bg="#9C27B0", fg="white", font=("Arial", 10, "bold")).pack(side=tk.LEFT, padx=5)
        
        tk.Button(morse_row2, text="Copy from Text", command=self.copy_text_to_morse, width=12,
                  bg="#607D8B", fg="white").pack(side=tk.LEFT, padx=15)
        
        self.morse_status = tk.StringVar(value="")
        ttk.Label(morse_row2, textvariable=self.morse_status, foreground="green").pack(side=tk.RIGHT, padx=5)
        
        # Canvas frame
        canvas_frame = ttk.LabelFrame(main, text="Canvas (1920x1080) - Checkerboard = Transparent", padding="5")
        canvas_frame.pack(fill=tk.BOTH, expand=True)
        
        # Canvas container for centering
        self.canvas_container = ttk.Frame(canvas_frame)
        self.canvas_container.pack(fill=tk.BOTH, expand=True)
        
        # Canvas
        self.canvas = tk.Canvas(self.canvas_container, bg="#333333", highlightthickness=1, highlightbackground="#666666")
        self.canvas.pack(expand=True)
        
        # Bind mouse events
        self.canvas.bind("<Button-1>", self.on_mouse_down)
        self.canvas.bind("<B1-Motion>", self.on_mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_mouse_up)
        self.canvas.bind("<Double-Button-1>", self.on_double_click)
    
    def on_freq_change(self):
        """Handle frequency change"""
        try:
            self.morse_frequency = int(self.freq_var.get())
            self.morse_frequency = max(300, min(1200, self.morse_frequency))
            self.morse_generator = MorseAudioGenerator(self.morse_frequency, self.morse_wpm)
            self.save_config()
        except:
            pass
    
    def on_wpm_change(self):
        """Handle WPM change"""
        try:
            self.morse_wpm = int(self.wpm_var.get())
            self.morse_wpm = max(5, min(40, self.morse_wpm))
            self.morse_generator = MorseAudioGenerator(self.morse_frequency, self.morse_wpm)
            self.save_config()
        except:
            pass
    
    def copy_text_to_morse(self):
        """Copy text from main text area to Morse input after converting"""
        current_text = self.text_entry.get("1.0", tk.END).strip()
        if current_text:
            # Convert text to Morse and put in single line
            morse = text_to_morse(current_text.replace('\n', ' '))
            self.morse_entry.delete(0, tk.END)
            self.morse_entry.insert(0, morse)
            self.morse_status.set("Copied and converted to Morse")
            self.root.after(2000, lambda: self.morse_status.set(""))
    
    def play_morse_audio(self):
        """Play Morse code audio in a separate thread"""
        if self.is_playing:
            return
        
        morse_code = self.morse_entry.get().strip()
        if not morse_code:
            self.morse_status.set("No Morse code to play")
            self.root.after(2000, lambda: self.morse_status.set(""))
            return
        
        self.is_playing = True
        self.play_btn.config(text="Playing...", state=tk.DISABLED)
        self.morse_status.set("Playing...")
        
        def play_thread():
            try:
                temp_file = os.path.join(os.path.expanduser("~"), ".temp_morse.wav")
                result = self.morse_generator.play_morse(morse_code, temp_file)
                if result:
                    # Fallback: file was saved but couldn't play
                    self.root.after(0, lambda: self.morse_status.set(f"Audio saved to {result}"))
            except Exception as e:
                self.root.after(0, lambda: self.morse_status.set(f"Error: {str(e)[:30]}"))
            finally:
                self.root.after(0, self.finish_playing)
        
        thread = threading.Thread(target=play_thread, daemon=True)
        thread.start()
    
    def finish_playing(self):
        """Reset play button after audio finishes"""
        self.is_playing = False
        self.play_btn.config(text="▶ Play", state=tk.NORMAL)
        if "Playing" in self.morse_status.get():
            self.morse_status.set("Done")
            self.root.after(2000, lambda: self.morse_status.set(""))
    
    def export_morse_wav(self):
        """Export Morse code audio to WAV file"""
        morse_code = self.morse_entry.get().strip()
        if not morse_code:
            self.morse_status.set("No Morse code to export")
            self.root.after(2000, lambda: self.morse_status.set(""))
            return
        
        path = filedialog.asksaveasfilename(
            defaultextension=".wav",
            filetypes=[("WAV files", "*.wav")],
            title="Export Morse Audio as WAV"
        )
        
        if path:
            try:
                self.morse_generator.save_wav(morse_code, path)
                self.morse_status.set(f"Exported: {os.path.basename(path)}")
                self.root.after(3000, lambda: self.morse_status.set(""))
            except Exception as e:
                self.morse_status.set(f"Error: {str(e)[:30]}")
                self.root.after(3000, lambda: self.morse_status.set(""))
    
    def convert_to_morse(self):
        """Convert current text to Morse code"""
        current_text = self.text_entry.get("1.0", tk.END).strip()
        if current_text:
            lines = current_text.split('\n')
            morse_lines = [text_to_morse(line) for line in lines]
            morse_text = '\n'.join(morse_lines)
            
            self.text_entry.delete("1.0", tk.END)
            self.text_entry.insert("1.0", morse_text)
            self.on_text_change()
            self.dropper_status.set("Converted to Morse code")
            self.root.after(2000, lambda: self.dropper_status.set(""))
    
    def convert_from_morse(self):
        """Convert Morse code back to text"""
        current_text = self.text_entry.get("1.0", tk.END).strip()
        if current_text:
            lines = current_text.split('\n')
            text_lines = [morse_to_text(line) for line in lines]
            plain_text = '\n'.join(text_lines)
            
            self.text_entry.delete("1.0", tk.END)
            self.text_entry.insert("1.0", plain_text)
            self.on_text_change()
            self.dropper_status.set("Converted from Morse code")
            self.root.after(2000, lambda: self.dropper_status.set(""))
    
    def set_align(self, align):
        self.text_align = align
        self.update_align_buttons()
        self.save_config()
        self.update_canvas()
    
    def update_align_buttons(self):
        for btn, val in [(self.align_left_btn, "left"), (self.align_center_btn, "center"), (self.align_right_btn, "right")]:
            if self.text_align == val:
                btn.config(relief=tk.SUNKEN, bg="#AADDFF")
            else:
                btn.config(relief=tk.RAISED, bg="SystemButtonFace")
    
    def on_spacing_change(self):
        try:
            self.line_spacing = float(self.spacing_var.get())
            self.line_spacing = max(0.5, min(3.0, self.line_spacing))
            self.save_config()
            self.update_canvas()
        except:
            pass
    
    def on_resize(self, event=None):
        if hasattr(self, '_resize_after_id') and self._resize_after_id is not None:
            try:
                self.root.after_cancel(self._resize_after_id)
            except:
                pass
        self._resize_after_id = self.root.after(50, self.fit_canvas)
    
    def fit_canvas(self):
        self.canvas_container.update_idletasks()
        available_width = self.canvas_container.winfo_width() - 20
        available_height = self.canvas_container.winfo_height() - 20
        
        if available_width < 100 or available_height < 100:
            return
        
        scale_x = available_width / 1920
        scale_y = available_height / 1080
        self.scale = min(scale_x, scale_y)
        
        display_width = int(1920 * self.scale)
        display_height = int(1080 * self.scale)
        
        self.canvas.config(width=display_width, height=display_height)
        
        self.update_canvas()
    
    def draw_checkerboard(self):
        self.canvas.delete("checker")
        checker_size = max(10, int(20 * self.scale))
        
        display_width = int(1920 * self.scale)
        display_height = int(1080 * self.scale)
        
        for y in range(0, display_height, checker_size):
            for x in range(0, display_width, checker_size):
                color = "#CCCCCC" if (x // checker_size + y // checker_size) % 2 == 0 else "#999999"
                self.canvas.create_rectangle(x, y, x + checker_size, y + checker_size, 
                                          fill=color, outline="", tags="checker")
    
    def update_canvas(self):
        self.draw_checkerboard()
        
        self.canvas.delete("text_element")
        self.canvas.delete("text_box")
        self.canvas.delete("resize_handle")
        
        scaled_x = self.text_x * self.scale
        scaled_y = self.text_y * self.scale
        scaled_size = max(8, int(self.font_size * self.scale))
        
        try:
            tk_font = font.Font(family=self.font_family, size=scaled_size)
        except:
            tk_font = font.Font(family="Arial", size=scaled_size)
        
        lines = self.text_content.split('\n')
        if self.flip_h:
            lines = [line[::-1] for line in lines]
        
        line_height = tk_font.metrics('linespace') * self.line_spacing
        total_height = line_height * len(lines)
        start_y = scaled_y - total_height / 2 + line_height / 2
        
        if self.vertical_stack:
            all_chars = list(self.text_content.replace('\n', ''))
            if self.flip_h:
                all_chars = all_chars[::-1]
            
            char_height = tk_font.metrics('linespace') * self.line_spacing
            total_char_height = char_height * len(all_chars)
            char_start_y = scaled_y - total_char_height / 2 + char_height / 2
            
            for i, char in enumerate(all_chars):
                char_y = char_start_y + i * char_height
                self.canvas.create_text(
                    scaled_x, char_y,
                    text=char,
                    font=tk_font,
                    fill=self.font_color,
                    anchor="center",
                    tags="text_element"
                )
        else:
            for i, line in enumerate(lines):
                line_y = start_y + i * line_height
                
                if self.text_align == "left":
                    anchor = "w"
                    line_x = scaled_x
                elif self.text_align == "right":
                    anchor = "e"
                    line_x = scaled_x
                else:
                    anchor = "center"
                    line_x = scaled_x
                
                self.canvas.create_text(
                    line_x, line_y,
                    text=line,
                    font=tk_font,
                    fill=self.font_color,
                    anchor=anchor,
                    tags="text_element"
                )
        
        bbox = self.canvas.bbox("text_element")
        if bbox:
            x1, y1, x2, y2 = bbox
            padding = 5;
            
            self.canvas.create_rectangle(
                x1 - padding, y1 - padding, x2 + padding, y2 + padding,
                outline="#00AAFF", width=2, dash=(5, 5), tags="text_box"
            )
            
            handle_size = 8
            handles = [
                (x1 - padding, y1 - padding, "nw"),
                (x2 + padding, y1 - padding, "ne"),
                (x1 - padding, y2 + padding, "sw"),
                (x2 + padding, y2 + padding, "se"),
            ]
            
            for hx, hy, corner in handles:
                self.canvas.create_rectangle(
                    hx - handle_size//2, hy - handle_size//2,
                    hx + handle_size//2, hy + handle_size//2,
                    fill="#00AAFF", outline="white", tags=f"resize_handle {corner}"
                )
        
        status = ""
        if self.flip_h:
            status += " [H-Flipped]"
        if self.vertical_stack:
            status += " [Vertical]"
        line_count = len(self.text_content.split('\n'))
        self.pos_var.set(f"Position: X={self.text_x}, Y={self.text_y} | Size: {self.font_size}pt | Lines: {line_count}{status}")
    
    def toggle_flip_h(self):
        self.flip_h = not self.flip_h
        self.flip_h_btn.config(relief=tk.SUNKEN if self.flip_h else tk.RAISED,
                               bg="#AADDFF" if self.flip_h else "SystemButtonFace")
        self.update_canvas()
    
    def toggle_vertical(self):
        self.vertical_stack = not self.vertical_stack
        self.vertical_btn.config(relief=tk.SUNKEN if self.vertical_stack else tk.RAISED,
                                 bg="#AADDFF" if self.vertical_stack else "SystemButtonFace")
        self.update_canvas()
    
    def on_mouse_down(self, event):
        if self.dropper_active:
            return
        
        cx = event.x
        cy = event.y
        
        items = self.canvas.find_overlapping(cx-5, cy-5, cx+5, cy+5)
        for item in items:
            tags = self.canvas.gettags(item)
            if "resize_handle" in tags:
                self.resizing = True
                for tag in tags:
                    if tag in ["nw", "ne", "sw", "se"]:
                        self.resize_handle = tag
                        break
                self.drag_start_x = cx
                self.drag_start_y = cy
                return
        
        text_bbox = self.canvas.bbox("text_element")
        if text_bbox:
            x1, y1, x2, y2 = text_bbox
            if x1 <= cx <= x2 and y1 <= cy <= y2:
                self.dragging = True
                self.drag_start_x = cx - (self.text_x * self.scale)
                self.drag_start_y = cy - (self.text_y * self.scale)
    
    def on_mouse_drag(self, event):
        if self.dropper_active:
            return
        
        cx = event.x
        cy = event.y
        
        if self.dragging:
            self.text_x = int((cx - self.drag_start_x) / self.scale)
            self.text_y = int((cy - self.drag_start_y) / self.scale)
            
            self.text_x = max(0, min(1920, self.text_x))
            self.text_y = max(0, min(1080, self.text_y))
            
            self.update_canvas()
        
        elif self.resizing:
            dx = cx - self.drag_start_x
            dy = cy - self.drag_start_y
            
            distance = (dx + dy) / 2
            
            if self.resize_handle in ["se", "ne"]:
                new_size = self.font_size + int(distance / (5 * self.scale))
            else:
                new_size = self.font_size - int(distance / (5 * self.scale))
            
            new_size = max(8, min(500, new_size))
            
            if new_size != self.font_size:
                self.font_size = new_size
                self.size_var.set(self.font_size)
                self.drag_start_x = cx
                self.drag_start_y = cy
                self.update_canvas()
    
    def on_mouse_up(self, event):
        self.dragging = False
        self.resizing = False
        self.resize_handle = None
    
    def on_double_click(self, event):
        self.text_entry.focus_set()
    
    def on_font_change(self):
        self.font_family = self.font_var.get()
        self.save_config()
        self.update_canvas()
    
    def on_size_change(self):
        try:
            self.font_size = int(self.size_var.get())
            self.font_size = max(8, min(500, self.font_size))
            self.save_config()
            self.update_canvas()
        except:
            pass
    
    def on_text_change(self):
        self.text_content = self.text_entry.get("1.0", tk.END).rstrip('\n')
        self.update_canvas()
    
    def center_text(self):
        self.text_x = 960
        self.text_y = 540
        self.update_canvas()
    
    def pick_color(self):
        color = colorchooser.askcolor(color=self.font_color, title="Choose Text Color")
        if color[1]:
            self.font_color = color[1]
            self.color_btn.config(bg=self.font_color)
            self.save_config()
            self.update_canvas()
    
    def activate_dropper(self):
        self.dropper_active = True
        self.dropper_status.set("Click anywhere on screen to pick color...")
        self.dropper_btn.config(relief=tk.SUNKEN, bg="#FFFF00")
        self.root.config(cursor="crosshair")
        self.root.after(100, self.start_screen_pick)
    
    def start_screen_pick(self):
        self.picker_window = tk.Toplevel(self.root)
        self.picker_window.attributes("-fullscreen", True)
        self.picker_window.attributes("-alpha", 0.01)
        self.picker_window.attributes("-topmost", True)
        self.picker_window.config(cursor="crosshair")
        
        self.picker_window.bind("<Button-1>", self.do_screen_pick)
        self.picker_window.bind("<Escape>", self.cancel_dropper)
    
    def do_screen_pick(self, event):
        x = self.picker_window.winfo_pointerx()
        y = self.picker_window.winfo_pointery()
        
        self.picker_window.destroy()
        
        try:
            img = ImageGrab.grab(bbox=(x, y, x+1, y+1))
            pixel = img.getpixel((0, 0))
            
            self.font_color = "#{:02x}{:02x}{:02x}".format(pixel[0], pixel[1], pixel[2])
            self.color_btn.config(bg=self.font_color)
            self.save_config()
            self.update_canvas()
        except Exception as e:
            print(f"Error picking color: {e}")
        
        self.end_dropper()
    
    def cancel_dropper(self, event=None):
        if hasattr(self, 'picker_window'):
            self.picker_window.destroy()
        self.end_dropper()
    
    def end_dropper(self):
        self.dropper_active = False
        self.dropper_status.set("")
        self.dropper_btn.config(relief=tk.RAISED, bg="SystemButtonFace")
        self.root.config(cursor="")
    
    def find_font_path(self, font_name):
        """Find the font file path for a given font family name"""
        font_dirs = [
            "C:/Windows/Fonts",
            os.path.expanduser("~/AppData/Local/Microsoft/Windows/Fonts"),
        ]
        
        extensions = ['.ttf', '.otf', '.TTF', '.OTF']
        
        search_name = font_name.lower().replace(" ", "")
        
        font_mappings = {
            'arial': 'arial',
            'arialblack': 'ariblk',
            'timesnewroman': 'times',
            'couriernew': 'cour',
            'verdana': 'verdana',
            'tahoma': 'tahoma',
            'georgia': 'georgia',
            'trebuchetms': 'trebuc',
            'impactregular': 'impact',
            'impact': 'impact',
            'comicsansms': 'comic',
            'lucidaconsole': 'lucon',
            'palatinolinotype': 'pala',
            'segoeui': 'segoeui',
            'calibri': 'calibri',
            'cambria': 'cambria',
            'consolas': 'consola',
        }
        
        mapped_name = font_mappings.get(search_name, search_name)
        
        for font_dir in font_dirs:
            if os.path.exists(font_dir):
                try:
                    for file in os.listdir(font_dir):
                        file_lower = file.lower()
                        file_base = os.path.splitext(file_lower)[0]
                        
                        if file_base == mapped_name or file_base == search_name:
                            for ext in extensions:
                                if file_lower.endswith(ext.lower()):
                                    return os.path.join(font_dir, file)
                        
                        if mapped_name in file_base or search_name in file_base:
                            for ext in extensions:
                                if file_lower.endswith(ext.lower()):
                                    return os.path.join(font_dir, file)
                except:
                    pass
        
        for font_dir in font_dirs:
            if os.path.exists(font_dir):
                try:
                    for file in os.listdir(font_dir):
                        file_lower = file.lower()
                        for word in font_name.lower().split():
                            if len(word) > 2 and word in file_lower:
                                for ext in extensions:
                                    if file_lower.endswith(ext.lower()):
                                        return os.path.join(font_dir, file)
                except:
                    pass
        
        return None
    
    def export_png(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".png",
            filetypes=[("PNG files", "*.png")],
            title="Export as PNG"
        )
        
        if not path:
            return
        
        img = Image.new("RGBA", (1920, 1080), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        
        font_path = self.find_font_path(self.font_family)
        
        try:
            if font_path and os.path.exists(font_path):
                pil_font = ImageFont.truetype(font_path, self.font_size)
            else:
                fallbacks = ["arial.ttf", "Arial.ttf", "segoeui.ttf", "tahoma.ttf"]
                pil_font = None
                for fb in fallbacks:
                    try:
                        pil_font = ImageFont.truetype(fb, self.font_size)
                        break
                    except:
                        continue
                
                if pil_font is None:
                    try:
                        pil_font = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", self.font_size)
                    except:
                        pil_font = ImageFont.load_default()
                
                self.dropper_status.set(f"Warning: Using fallback font ('{self.font_family}' not found)")
                self.root.after(3000, lambda: self.dropper_status.set(""))
        except Exception as e:
            pil_font = ImageFont.load_default()
            self.dropper_status.set(f"Font error: {e}")
            self.root.after(3000, lambda: self.dropper_status.set(""))
        
        hex_color = self.font_color.lstrip('#')
        rgb = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
        rgba = rgb + (255,)
        
        lines = self.text_content.split('\n')
        if self.flip_h:
            lines = [line[::-1] for line in lines]
        
        bbox = draw.textbbox((0, 0), "Mg", font=pil_font)
        line_height = (bbox[3] - bbox[1]) * self.line_spacing
        
        if self.vertical_stack:
            all_chars = list(self.text_content.replace('\n', ''))
            if self.flip_h:
                all_chars = all_chars[::-1]
            
            total_height = line_height * len(all_chars)
            start_y = self.text_y - total_height / 2
            
            for i, char in enumerate(all_chars):
                char_bbox = draw.textbbox((0, 0), char, font=pil_font)
                char_width = char_bbox[2] - char_bbox[0]
                char_x = self.text_x - char_width / 2
                char_y = start_y + i * line_height
                draw.text((char_x, char_y), char, font=pil_font, fill=rgba)
        else:
            total_height = line_height * len(lines)
            start_y = self.text_y - total_height / 2
            
            line_widths = []
            for line in lines:
                if line:
                    bbox = draw.textbbox((0, 0), line, font=pil_font)
                    line_widths.append(bbox[2] - bbox[0])
                else:
                    line_widths.append(0)
            
            max_width = max(line_widths) if line_widths else 0
            
            for i, line in enumerate(lines):
                if not line:
                    continue
                
                line_bbox = draw.textbbox((0, 0), line, font=pil_font)
                line_width = line_bbox[2] - line_bbox[0]
                line_y = start_y + i * line_height
                
                if self.text_align == "left":
                    line_x = self.text_x - max_width / 2
                elif self.text_align == "right":
                    line_x = self.text_x + max_width / 2 - line_width
                else:
                    line_x = self.text_x - line_width / 2
                
                draw.text((line_x, line_y), line, font=pil_font, fill=rgba)
        
        img.save(path, "PNG")
        
        self.dropper_status.set(f"Exported: {os.path.basename(path)}")
        self.root.after(3000, lambda: self.dropper_status.set(""))


if __name__ == "__main__":
    root = tk.Tk()
    app = TextOverlayApp(root)
    root.mainloop()