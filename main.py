#!/usr/bin/env python3
"""
Audiobook Generator - Converts EPUB files to audio using Kokoro TTS
"""
from kokoro import KPipeline
import soundfile as sf
import sounddevice as sd
from ebooklib import epub, ITEM_DOCUMENT
from bs4 import BeautifulSoup
import os
import re


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


def generate_audiobook(epub_path, output_dir="audiobook_output", voice='bm_daniel', speed=1, play_audio=False):
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
    
    # Extract chapters
    print(f"Reading EPUB file: {epub_path}")
    chapters = extract_chapters_from_epub(epub_path)
    print(f"\nFound {len(chapters)} chapters\n")
    
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
            import numpy as np
            full_audio = np.concatenate(chapter_audio)
            
            # Save chapter audio
            output_file = os.path.join(output_dir, f"chapter_{chapter_num:02d}.wav")
            sf.write(output_file, full_audio, 24000)
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
    # Replace 'your_book.epub' with your actual EPUB file path
    epub_file = "ebooks/the-woman-in-white.epub"
    
    if os.path.exists(epub_file):
        generate_audiobook(
            epub_path=epub_file,
            output_dir="audiobook_output",
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
