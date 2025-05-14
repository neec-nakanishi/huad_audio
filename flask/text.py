import speech_recognition as sr  # 音声認識ライブラリ
from pydub import AudioSegment  # 音声ファイルを扱うためのライブラリ

def convert_wav_to_text(wav_file):
    # 音声認識のためのRecognizerオブジェクトを作成
    recognizer = sr.Recognizer()
    
    # WAVファイルをAudioSegmentで読み込む
    audio = AudioSegment.from_wav(wav_file)
    
    # AudioSegmentをAudioDataに変換
    audio_data = sr.AudioData(audio.raw_data, audio.frame_rate, audio.sample_width)

    # 音声データをテキストに変換
    try:
        # Google音声認識APIを使用して音声を認識し、日本語を指定
        text = recognizer.recognize_google(audio_data, language='ja-JP')  
        return text  # 認識したテキストを返す
    except sr.UnknownValueError:
        # 音声を理解できない場合の処理
        return "音声を理解できませんでした。"
    except sr.RequestError as e:
        # APIへの接続エラーが発生した場合の処理
        return f"音声認識サービスに接続できませんでした: {e}"
