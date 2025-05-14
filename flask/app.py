from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_file
from flask_sqlalchemy import SQLAlchemy
from text import convert_wav_to_text  # text.pyから音声認識の関数をインポート
import pandas as pd
import os
from pydub import AudioSegment
from flask_migrate import Migrate
from audio_analysis import AudioAnalysis  # audio_analysisモジュールをインポート


app = Flask(__name__,static_folder='./templates/images')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///trainees.db'
app.config['SECRET_KEY'] = 'your_secret_key'


db = SQLAlchemy(app)
migrate = Migrate(app, db)

# 保存するディレクトリを指定
AUDIO_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'audio')
if not os.path.exists(AUDIO_FOLDER):
    os.makedirs(AUDIO_FOLDER)

@app.route('/save_audio', methods=['POST'])
def save_audio():
    if 'audio' not in request.files or 'trainee_id' not in request.form or 'recording_count' not in request.form:
        return jsonify({'message': '必要なデータが不足しています。'}), 400

    audio_file = request.files['audio']
    filename = audio_file.filename
    trainee_id = int(request.form['trainee_id'])
    recording_count = int(request.form['recording_count']) #審査回数を受け取る

    #ファイルパスを作成
    wav_filename = filename.replace(".webm", ".wav")
    wav_path = os.path.join(AUDIO_FOLDER, wav_filename)

    #同じ研修生IDと録音回数で音声データを検索
    existing_audio = AudioFile.query.filter_by(trainee_id=trainee_id, recording_count=recording_count).first()
    
    #一時的に保存
    temp_path = os.path.join(AUDIO_FOLDER, filename)
    audio_file.save(temp_path)

    try:
        audio = AudioSegment.from_file(temp_path, format="webm")
        audio.export(wav_path,format="wav")
    finally:
        os.remove(temp_path)

    if existing_audio:
        #既存データを更新
        existing_audio.file_path = wav_path

    else:
        #新規録音データを作成
        new_audio_file = AudioFile(
            file_path=wav_path,
            trainee_id=trainee_id,
            recording_count=recording_count #回数を保存
        )
        db.session.add(new_audio_file)
    
    db.session.commit()

    # CSVファイルを作成
    trainee = Trainee.query.get(trainee_id)
    audio_files = AudioFile.query.filter_by(trainee_id=trainee_id).all()
    wav_files = [audio.file_path for audio in audio_files]
    output_dir = 'flask/templates/images/static'
    analyzer = AudioAnalysis(trainee.name, wav_files, output_dir)
    analyzer.generate_csv() # 録音終了時にcsvファイルを生成

    return jsonify({'message': f'録音が保存され、CSVファイルが作成されました。'}), 200    

# 研修生テーブル
class Trainee(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(20), nullable=False)
    audio_files = db.relationship(
        'AudioFile',
        backref='trainee',
        lazy=True,
        cascade="all, delete")

# 音声ファイルテーブル
class AudioFile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    file_path = db.Column(db.String(200), nullable=False)
    trainee_id = db.Column(db.Integer, db.ForeignKey('trainee.id'), nullable=False)
    recording_count = db.Column(db.Integer, nullable=False) #録音回数
    transcriptions = db.relationship('Transcription', backref='audio', lazy=True, cascade="all, delete")

# テキスト化データテーブル
class Transcription(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    text_data = db.Column(db.Text, nullable=False)
    audio_id = db.Column(db.Integer, db.ForeignKey('audio_file.id'), nullable=False)
    recording_count = db.Column(db.Integer, nullable=False) #録音回数を示すカラムを追加

# データベースの初期化
with app.app_context():
    db.create_all()

# メイン画面
@app.route('/')
def index():
    return render_template('main_win.html')

# 録音画面
@app.route('/record')
def record():
    trainees = Trainee.query.all()  # データベースからすべての研修生データを取得
    recorded_counts = {
        trainee.id: [
            audio.recording_count for audio in trainee.audio_files
        ]
        for trainee in trainees
    }
    return render_template('rec_win.html', trainees=trainees, recorded_counts=recorded_counts)

# 研修生選択画面
@app.route('/choice')
def results():
    trainees = Trainee.query.all()  # データベースからすべての研修生データを取得
    return render_template('choise_win.html', trainees=trainees)

# 結果表示
@app.route('/result', methods=['GET'])
def result():
    trainee_id = request.args.get('trainee_id')
    trainee = db.session.get(Trainee, trainee_id)

    if not trainee:
        flash('研修生が見つかりません')
        return redirect(url_for('results'))

    # CSVファイルのパス
    output_dir = 'flask/templates/images/static'
    csv_path = os.path.join(output_dir, trainee.name, f"{trainee.name}_features.csv")

    if not os.path.exists(csv_path):
        flash('CSVファイルが見つかりません。録音データが不足しています。')
        return redirect(url_for('results'))

    # グラフ生成
    analyzer = AudioAnalysis(trainee.name, [], output_dir)
    analyzer.generate_graphs_from_csv(csv_path) # CSVからグラフを生成

    # グラフファイルのパスを辞書として準備
    graph_files = {
        "音量の変化": f"images/static/{trainee.name}/{trainee.name}_音量の変化.png",
        "高さの変化": f"images/static/{trainee.name}/{trainee.name}_高さの変化.png",
        "速さの変化": f"images/static/{trainee.name}/{trainee.name}_速さの変化.png",
        "明瞭さの変化": f"images/static/{trainee.name}/{trainee.name}_明瞭さの変化.png",
    }

    # traineeを渡す
    return render_template('result_win.html', graph_files=graph_files, trainee=trainee)

# テキスト表示
@app.route('/text', methods=['GET'])  # GETおよびPOSTリクエストを受け入れる
def text_data():
    trainee_id = request.args.get('trainee_id')
    recording_count = request.args.get('count', '1') #デフォルトで1回目
    trainee = Trainee.query.get(trainee_id)

    if not trainee:
        flash('研修生が見つかりません')
        return redirect(url_for('results'))

    #録音回数に対応するテキストデータを取得
    transcription = Transcription.query.join(AudioFile).filter(
        AudioFile.trainee_id == trainee_id,
        AudioFile.recording_count == int(recording_count),
        Transcription.recording_count == int(recording_count)
    ).first()

    #すでにテキスト化されている場合はデータをそのまま表示
    if transcription:
        recognized_text = transcription.text_data
    else:
        #該当する録音回数の音声ファイルを取得
        target_audio = AudioFile.query.filter_by(
            trainee_id=trainee_id,
            recording_count=int(recording_count)
        ).first()

        if not target_audio:
            return render_template(
                'text_win.html',
                recognized_text="該当の音声データがありません。",
                trainee=trainee,
                recording_count=recording_count
            )
        
        #音声データをテキスト化
        recognized_text = convert_wav_to_text(target_audio.file_path)

        #テキストデータをデータベースに保存
        new_transcription = Transcription(
            text_data=recognized_text,
            audio_id=target_audio.id,
            recording_count=int(recording_count)
        )
        db.session.add(new_transcription)
        db.session.commit()

    return render_template(
        'text_win.html',
        recognized_text=recognized_text,
        trainee=trainee,
        recording_count=recording_count
    )

# 研修生表示画面
@app.route('/members')
def members():
    trainees = Trainee.query.all()  # すべての研修生を取得
    return render_template('memberlist_win.html', trainees=trainees)

# Excelファイルから研修生データをインポートする
@app.route('/import', methods=['POST'])
def import_data():
    if 'file' not in request.files:
        flash('ファイルが選択されていません。')
        return redirect(url_for('members'))

    file = request.files['file']
    if file.filename == '':
        flash('有効なファイルを選択してください。')
        return redirect(url_for('members'))

    # Excelファイルの読み込み
    df = pd.read_excel(file)

    # データベースに追加
    for _, row in df.iterrows():
        trainee = Trainee(name=row['氏名'])  # Excelファイルの列名に応じて修正
        db.session.add(trainee)

    db.session.commit()
    flash('データがインポートされました。')
    return redirect(url_for('members'))

# 研修生データの削除
@app.route('/delete/<int:id>')
def delete(id):
    trainee = Trainee.query.get(id)
    if not trainee:
        flash('研修生が見つかりません')
        return redirect(url_for('members'))
    
    # 研修生名フォルダを特定
    trainee_dir = os.path.join('flask/templates/images/static', trainee.name)

    # フォルダ内のCSVファイルとPNGファイルを削除
    if os.path.exists(trainee_dir):
        for file_name in os.listdir(trainee_dir):
            file_path = os.path.join(trainee_dir, file_name)
            if os.path.isfile(file_path) and (file_name.endswith('.csv') or file_name.endswith('.png')):
                os.remove(file_path)
        # フォルダ自体を削除
        os.rmdir(trainee_dir)

    #関連するAudioFileとTranscriptionを削除
    for audio_file in trainee.audio_files:
        #音声ファイルの物理ファイルを削除
        if os.path.exists(audio_file.file_path):
            os.remove(audio_file.file_path)

        #テキスト化データを削除
        for transcription in audio_file.transcriptions:
            db.session.delete(transcription)

        #AudioFileのデータを削除
        db.session.delete(audio_file)

    #研修生データを削除
    db.session.delete(trainee)
    db.session.commit()
    flash(f'研修生 {trainee.name} を削除しました。')
    return redirect(url_for('members'))

# 研修生データの一括削除
# 研修生データの一括削除
@app.route('/delete_all', methods=['POST'])
def delete_all():
    try:
        #すべてのTraineeを取得
        trainees = Trainee.query.all()
        for trainee in trainees:
            # 研修生名フォルダを特定
            trainee_dir = os.path.join('flask/templates/images/static', trainee.name)

            # フォルダ内のCSVファイルとPNGファイルを削除
            if os.path.exists(trainee_dir):
                for file_name in os.listdir(trainee_dir):
                    file_path = os.path.join(trainee_dir, file_name)
                    if os.path.isfile(file_path) and (file_name.endswith('.csv') or file_name.endswith('.png')):
                        os.remove(file_path)
                # フォルダ自体を削除
                os.rmdir(trainee_dir)

            #各研修生の関連データを削除
            for audio_file in trainee.audio_files:
                if os.path.exists(audio_file.file_path):
                    os.remove(audio_file.file_path)

                for transcription in audio_file.transcriptions:
                    db.session.delete(transcription)
                
                db.session.delete(audio_file)

            db.session.delete(trainee)

        db.session.commit()
        flash('すべてのデータが削除されました。')
    except Exception as e:
        db.session.rollback()
        flash('データの削除に失敗しました。')
    return redirect(url_for('members'))

@app.route('/trainee_audio/<int:trainee_id>')
def trainee_audio(trainee_id):
    """
    研修生に紐づく音声ファイルを表示する画面。
    音声ファイルを再生するためのプレイヤーを提供
    """
    trainee = Trainee.query.get(trainee_id)
    if not trainee:
        flash('研修生が見つかりません')
        return redirect(url_for('members'))

    #この研修生に関連付けられた音声ファイルを取得
    audio_files = AudioFile.query.filter_by(trainee_id=trainee_id).all()

    return render_template('trainee_audio.html', trainee=trainee, audio_files=audio_files)

@app.route('/serve_audio/<int:audio_id>', methods=['GET'])
def serve_audio(audio_id):
    """
    音声ファイルを提供するエンドポイント。
    """
    audio_file = AudioFile.query.get(audio_id)
    if not audio_file or not os.path.exists(audio_file.file_path):
        return jsonify({"message": "音声ファイルが見つかりません。"}), 404

    try:
        #ファイルを提供
        return send_file(audio_file.file_path, as_attachment=False)
    except Exception as e:
        return jsonify({"message": f"ファイル提供中にエラーが発生しました: {e}"}), 500

@app.route('/delete_audio/<int:id>', methods=['GET'])
def delete_audio(id):
    """
    指定された音声ファイルを削除するエンドポイント
    """
    audio_file = AudioFile.query.get(id)
    if not audio_file:
        flash('音声ファイルが見つかりません。')
        return redirect(url_for('trainee_audio', trainee_id=audio_file.trainee_id))

    #音声ファイルの物理ファイルも削除
    if os.path.exists(audio_file.file_path):
        os.remove(audio_file.file_path)

    #データベースから削除
    db.session.delete(audio_file)
    db.session.commit()

    flash('音声ファイルが削除されました')
    return redirect(url_for('trainee_audio', trainee_id=audio_file.trainee_id))

if __name__ == "__main__":
    app.run(debug=True)
