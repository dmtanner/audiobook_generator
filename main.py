# !pip install -q kokoro>=0.9.2 soundfile sounddevice
# !apt-get -qq -y install espeak-ng > /dev/null 2>&1
from kokoro import KPipeline
import soundfile as sf
import sounddevice as sd

text = '''
It was the last day of July. The long hot summer was drawing to
a close; and we, the weary pilgrims of the London pavement, were
beginning to think of the cloud-shadows on the corn-fields, and the
autumn breezes on the sea-shore.
'''

pipeline = KPipeline(lang_code='a')

generator = pipeline(text, voice='bm_daniel', speed=1, split_pattern=r'\n\n+')
for i, (gs, ps, audio) in enumerate(generator):
    print(i, gs, ps)
    # Save audio to file
    sf.write(f'{i}.wav', audio, 24000)
    # Play audio out loud
    sd.play(audio, samplerate=24000)
    sd.wait()  # Wait until audio finishes playing
