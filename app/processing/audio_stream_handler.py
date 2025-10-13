import threading
import queue
import sounddevice as sd
import numpy as np
from faster_whisper import WhisperModel
import tempfile
import os
from scipy.io.wavfile import write

# --- Настройки ---
MODEL_NAME = "tiny"       # tiny/base/small/medium
SEGMENT_DURATION = 1      # длительность сегмента в секундах
SAMPLE_RATE = 16000       # частота дискретизации
DEVICE = "cpu"            # можно "auto", "mps" или "cuda" если доступно

# --- Инициализация ---
model = WhisperModel(MODEL_NAME, device=DEVICE)
audio_queue = queue.Queue()

class ConversationBuffer:
    def __init__(self, max_size=10):
        self.buffer = []
        self.max_size = max_size

    def add(self, text):
        self.buffer.append(text)
        if len(self.buffer) > self.max_size:
            self.buffer.pop(0)

    def get_context(self):
        return " ".join(self.buffer)

buffer = ConversationBuffer()

def audio_callback(indata, frames, time, status):
    """Записываем аудио в очередь"""
    if status:
        print(status)
    audio_queue.put(indata.copy())

def save_temp_wav(audio_data):
    """Сохраняем сегмент во временный WAV файл"""
    tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
    # нормализуем до int16
    audio_int16 = np.int16(audio_data / np.max(np.abs(audio_data)) * 32767)
    write(tmp_file.name, SAMPLE_RATE, audio_int16)
    return tmp_file.name

def transcribe_chunk(wav_path):
    """Фоновая транскрипция"""
    try:
        segments, info = model.transcribe(wav_path, beam_size=1, vad_filter=True)
        text = " ".join([s.text.strip() for s in segments if s.text.strip()])
        if text:
            buffer.add(text)
            print(f"📝 Распознано: {text}")
    except Exception as e:
        print(f"Ошибка транскрипции: {e}")
    finally:
        if os.path.exists(wav_path):
            os.remove(wav_path)

def main():
    print("🎤 Запись с микрофона. Говорите что-нибудь...")
    try:
        with sd.InputStream(channels=1, samplerate=SAMPLE_RATE, callback=audio_callback):
            while True:
                segment = []
                # Собираем данные на SEGMENT_DURATION секунд
                while len(segment) < SEGMENT_DURATION * SAMPLE_RATE:
                    data = audio_queue.get()
                    segment.append(data)
                segment = np.concatenate(segment, axis=0)
                
                # Сохраняем во временный файл
                wav_path = save_temp_wav(segment)
                
                # 🔥 Запускаем транскрипцию в фоне
                threading.Thread(
                    target=transcribe_chunk,
                    args=(wav_path,),
                    daemon=True
                ).start()

    except KeyboardInterrupt:
        print("\n🛑 Остановлено пользователем.")
        print("💬 Контекст разговора:")
        print(buffer.get_context())

if __name__ == "__main__":
    main()