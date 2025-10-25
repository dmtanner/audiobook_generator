#!/usr/bin/env python3
"""
Audiobook Generator - Converts EPUB files to audio using Kokoro TTS
"""
from kokoro import KPipeline
import soundfile as sf
import sounddevice as sd
from ebooklib import epub, ITEM_DOCUMENT
from bs4 import BeautifulSoup
from pydub import AudioSegment
from mutagen.mp4 import MP4, MP4Cover
import os
import re
import numpy as np
import tempfile


def get_book_metadata(epub_path):
    """
    Extract metadata from an EPUB file.
    
    Args:
        epub_path: Path to the EPUB file
        
    Returns:
        Dictionary with metadata (title, author, etc.)
    """
    book = epub.read_epub(epub_path)
    
    metadata = {
        'title': book.get_metadata('DC', 'title')[0][0] if book.get_metadata('DC', 'title') else 'Unknown Title',
        'author': book.get_metadata('DC', 'creator')[0][0] if book.get_metadata('DC', 'creator') else 'Unknown Author',
        'publisher': book.get_metadata('DC', 'publisher')[0][0] if book.get_metadata('DC', 'publisher') else '',
        'date': book.get_metadata('DC', 'date')[0][0] if book.get_metadata('DC', 'date') else '',
        'language': book.get_metadata('DC', 'language')[0][0] if book.get_metadata('DC', 'language') else 'en',
    }
    
    return metadata


def extract_chapters_from_epub(epub_path):
    """
    Extract chapters from an EPUB file.
    
    Args:
        epub_path: Path to the EPUB file
        
    Returns:
        List of tuples (chapter_number, chapter_title, chapter_text)
    """
    book = epub.read_epub(epub_path)
    chapters = []
    
    chapter_num = 0
    for item in book.get_items():
        if item.get_type() == ITEM_DOCUMENT:
            # Parse HTML content
            soup = BeautifulSoup(item.get_content(), 'html.parser')
            
            # Extract text
            text = soup.get_text()
            
            # Clean up text - remove excessive whitespace
            text = re.sub(r'\n\s*\n', '\n\n', text)
            text = text.strip()
            
            # Skip empty chapters
            if not text or len(text) < 50:
                continue
            
            # Try to get chapter title
            title = item.get_name()
            h1 = soup.find(['h1', 'h2', 'h3'])
            if h1:
                title = h1.get_text().strip()
            
            chapter_num += 1
            chapters.append((chapter_num, title, text))
            print(f"Extracted Chapter {chapter_num}: {title}")
    
    return chapters


def save_audio_as_m4b(audio_data, output_file, metadata):
    """
    Save audio data as M4B format with metadata.
    
    Args:
        audio_data: numpy array of audio samples
        output_file: Path to output M4B file
        metadata: Dictionary containing book metadata (title, author, chapter_num, etc.)
    """
    # Create a temporary WAV file
    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_wav:
        temp_wav_path = temp_wav.name
        sf.write(temp_wav_path, audio_data, 24000)
    
    try:
        # Load the WAV file with pydub
        audio = AudioSegment.from_wav(temp_wav_path)
        
        # Export as M4B (AAC codec in MP4 container)
        # M4B is essentially M4A with audiobook metadata
        audio.export(
            output_file,
            format='ipod',  # iPod format creates M4A/M4B compatible files
            codec='aac',
            bitrate='64k',  # Good quality for spoken word
            parameters=['-strict', '-2']  # Allow experimental AAC encoder
        )
        
        # Add metadata using mutagen
        audio_file = MP4(output_file)
        
        # Set standard tags
        if 'album' in metadata:
            audio_file['\xa9alb'] = metadata['album']  # Album (book title)
        if 'title' in metadata:
            audio_file['\xa9nam'] = metadata['title']  # Track title (chapter title)
        if 'author' in metadata:
            audio_file['\xa9ART'] = metadata['author']  # Artist (author)
            audio_file['aART'] = metadata['author']    # Album artist
        if 'genre' in metadata:
            audio_file['\xa9gen'] = metadata['genre']  # Genre
        if 'date' in metadata and metadata['date']:
            audio_file['\xa9day'] = metadata['date']  # Release date
        if 'comment' in metadata:
            audio_file['\xa9cmt'] = metadata['comment']  # Comment
        
        # Track number (chapter number)
        if 'track_num' in metadata and 'total_tracks' in metadata:
            audio_file['trkn'] = [(metadata['track_num'], metadata['total_tracks'])]
        
        # Mark as audiobook
        audio_file['stik'] = [2]  # 2 = Audiobook in iTunes
        
        audio_file.save()
        
    finally:
        # Clean up temporary file
        if os.path.exists(temp_wav_path):
            os.remove(temp_wav_path)


def generate_audiobook(epub_path, output_dir="audiobooks", voice='af_heart', speed=1, play_audio=False):
    """
    Generate audiobook from EPUB file.
    
    Args:
        epub_path: Path to the EPUB file
        output_dir: Directory to save audio files
        voice: Voice to use for TTS
        speed: Speech speed
        play_audio: Whether to play audio as it's generated
    """
    # Create output directory
    os.makedirs(output_dir, exist_ok=True)
    
    # Extract book metadata
    print(f"Reading EPUB file: {epub_path}")
    book_metadata = get_book_metadata(epub_path)
    print(f"Book: {book_metadata['title']} by {book_metadata['author']}")
    
    # Extract chapters
    chapters = extract_chapters_from_epub(epub_path)
    print(f"\nFound {len(chapters)} chapters\n")
    total_chapters = len(chapters)
    
    # Initialize TTS pipeline
    pipeline = KPipeline(lang_code='a')
    
    # Process each chapter
    for chapter_num, title, text in chapters:
        print(f"\n{'='*60}")
        print(f"Processing Chapter {chapter_num}: {title}")
        print(f"{'='*60}")
        print(f"Text length: {len(text)} characters")
        
        # Generate audio for this chapter
        generator = pipeline(text, voice=voice, speed=speed, split_pattern=r'\n\n+')
        
        chapter_audio = []
        for i, (gs, ps, audio) in enumerate(generator):
            print(f"  Segment {i}: {len(audio)} samples")
            chapter_audio.append(audio)
            
            if play_audio:
                sd.play(audio, samplerate=24000)
                sd.wait()
        
        # Concatenate all audio segments for this chapter
        if chapter_audio:
            full_audio = np.concatenate(chapter_audio)
            
            # Prepare metadata for this chapter
            chapter_metadata = {
                'album': book_metadata['title'],
                'title': f"Chapter {chapter_num}: {title}",
                'author': book_metadata['author'],
                'genre': 'Audiobook',
                'date': book_metadata['date'],
                'track_num': chapter_num,
                'total_tracks': total_chapters,
                'comment': f"Generated with Kokoro TTS"
            }
            
            # Save chapter audio as M4B
            output_file = os.path.join(output_dir, f"chapter_{chapter_num:02d}.m4b")
            print(f"Encoding to M4B format...")
            save_audio_as_m4b(full_audio, output_file, chapter_metadata)
            print(f"Saved: {output_file}")
    
    print(f"\n{'='*60}")
    print(f"Audiobook generation complete!")
    print(f"Output directory: {output_dir}")
    print(f"{'='*60}")


def test_audio():
    text = '''
      "I hope you come here good-humouredly determined to make the best of your
      position,” continued the lady. “You will have to begin this morning by
      putting up with no other company at breakfast than mine. My sister is in
      her own room, nursing that essentially feminine malady, a slight headache;"
    '''
    pipeline = KPipeline(lang_code='a')
    generator = pipeline(text, voice='af_heart', speed=1, split_pattern=r'\n\n+')
    for i, (gs, ps, audio) in enumerate(generator):
        print(f"  Segment {i}: {len(audio)} samples")
        sd.play(audio, samplerate=24000)
        sd.wait()

if __name__ == "__main__":
    # test_audio()
    # Example usage
    # Replace with your actual EPUB file path
    title = "the-art-of-war"
    epub_file = f"ebooks/{title}.epub"
    
    if os.path.exists(epub_file):
        generate_audiobook(
            epub_path=epub_file,
            output_dir=f"audiobooks/{title}",
            voice='bm_daniel',
            speed=1,
            play_audio=False  # Set to True if you want to hear it as it generates
        )
    else:
        print(f"Error: EPUB file not found: {epub_file}")
        print("\nUsage:")
        print("1. Place your EPUB file in this directory")
        print("2. Update the 'epub_file' variable with your filename")
        print("3. Run: python main.py")
